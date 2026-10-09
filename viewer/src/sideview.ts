import type { Pos } from "./events.ts";
import { ballOnFlight } from "./flights.ts";
import { sampleAt, type Sample } from "./interpolate.ts";
import { teamOf, type ReplayMeta, type TeamSide } from "./meta.ts";
import { KEEPER_COLOURS, pickKits, type Kit } from "./palette.ts";
import { HEIGHT, WIDTH } from "./pitch.ts";
import type { Extras } from "./scene.ts";
import { drawProfilePlayer } from "./profile.ts";
import { drawBall, drawCarrierMark, drawFocusMark, drawTrail, type Dress } from "./sprites.ts";
import type { Frame } from "./store.ts";

/**
 * The broadcast view: the pitch seen from a gantry on the touchline, far side up and near side down.
 *
 * World coordinates are the pitch's own (x along its length, y across it, both 0..1, plus a height in
 * metres). Depth gives scale: the far touchline is drawn about 60% as large as the near one, and
 * rows are spaced the way a real camera spaces them, so the pitch is a trapezoid. The camera pans
 * along the pitch only.
 */
export type SideMode = "wide" | "broadcast";

interface Geometry {
  /** Screen row of the far and near touchline. */
  farY: number;
  nearY: number;
  /** Pixels per metre along the near touchline. */
  ppm: number;
}

const GEOMETRY: Record<SideMode, Geometry> = {
  wide: { farY: 104, nearY: 204, ppm: 2.95 },
  broadcast: { farY: 70, nearY: 212, ppm: 6.2 },
};

const SCALE_FAR = 0.62;
const SCALE_NEAR = 1;
const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;
const CENTRE_X = WIDTH / 2;
/** The top-down view's pixels per metre, which pose offsets and flight heights are measured in. */
const TOP_DOWN_PPM = 300 / PITCH_LENGTH_M;
/** A full-size player is 11 pixels for 1.8 m: this many pixels to the metre. */
const FULL_SIZE_PPM = 6.1;
/** Nobody is drawn smaller than this share of full size: smaller would be too few pixels to read. */
const MIN_SCALE = 0.62;
/** The carrier and focus marks come in two sizes: the larger above this scale. */
const BIG_MARK_FROM = 0.85;

/** How large to draw a player at a depth with this many pixels to the metre. */
function sizeAt(ppm: number): number {
  return Math.max(ppm / FULL_SIZE_PPM, MIN_SCALE);
}
/** The camera follows the ball as it was over this many seconds, so it glides. */
const FOLLOW_SECONDS = 1.5;
const FOLLOW_SAMPLES = 4;

const GRASS_LIGHT = "#3f8f3f";
const GRASS_DARK = "#388538";
const RUN_OFF = "#2f7433";
const LINE = "#d9ecd9";
const STAND = "#1d2b3a";
const CROWD = ["#3a2a3f", "#2f3e5e", "#5a2f35", "#6b6f78", "#4d5a3c", "#7a6a3a", "#2b3a4a", "#8a8f98"];
const BOARDS = ["#c8102e", "#0b3d91", "#f2c200", "#e8e8e8", "#006b3c"];
const STRIPES = 10;
const BOARD_ROWS = 6;
const BOARD_WIDTH_M = 4.2;

export function geometryOf(mode: SideMode): Geometry {
  return GEOMETRY[mode];
}

function scaleAt(y: number): number {
  return SCALE_FAR + (SCALE_NEAR - SCALE_FAR) * y;
}

/** 0 at the far touchline, 1 at the near one, growing faster toward the camera. */
function depth(y: number): number {
  const a = (SCALE_NEAR - SCALE_FAR) / 2;
  return (SCALE_FAR * y + a * y * y) / (SCALE_FAR + a);
}

/** The pitch row (0 far, 1 near, beyond 1 is the run-off) that a screen row shows. */
function pitchRowAt(geo: Geometry, screenY: number): number {
  const a = (SCALE_NEAR - SCALE_FAR) / 2;
  const u = (screenY - geo.farY) / (geo.nearY - geo.farY);
  return (-SCALE_FAR + Math.sqrt(SCALE_FAR * SCALE_FAR + 4 * a * (SCALE_FAR + a) * u)) / (2 * a);
}

export interface Projected {
  x: number;
  y: number;
  /** Pixels per metre at this depth. */
  ppm: number;
}

/** Where a point of the pitch, `heightM` above the grass, is on screen with the camera at `camX`. */
export function project(mode: SideMode, camX: number, x: number, y: number, heightM = 0): Projected {
  const geo = GEOMETRY[mode];
  const scale = scaleAt(y);
  const ppm = geo.ppm * scale;
  const ground = geo.farY + (geo.nearY - geo.farY) * depth(y);
  return { x: CENTRE_X + (x - camX) * PITCH_LENGTH_M * ppm, y: ground - heightM * ppm, ppm };
}

/** The pan limits: the camera keeps the goal lines near the edge of the screen at most. */
function panRange(mode: SideMode): { low: number; high: number } {
  if (mode === "wide") return { low: 0.5, high: 0.5 };
  const half = WIDTH / 2 / (GEOMETRY.broadcast.ppm * PITCH_LENGTH_M * SCALE_NEAR);
  return { low: half * 0.85, high: 1 - half * 0.85 };
}

/** Where the camera looks along the pitch at `t`: the recent ball, or the player being followed. */
export function sideCameraX(frames: readonly Frame[], t: number, mode: SideMode, focusId: string | null): number {
  const range = panRange(mode);
  if (range.low === range.high) return range.low;
  let total = 0;
  let seen = 0;
  for (let step = 0; step < FOLLOW_SAMPLES; step++) {
    const sample = sampleAt(frames, t - (step * FOLLOW_SECONDS) / (FOLLOW_SAMPLES - 1));
    if (sample === null) continue;
    const player = focusId === null ? undefined : sample.players.find((candidate) => candidate.id === focusId);
    total += player === undefined ? sample.ballX : player.x;
    seen++;
  }
  const centre = seen === 0 ? 0.5 : total / seen;
  return Math.min(Math.max(centre, range.low), range.high);
}

function hash(x: number, y: number): number {
  let value = Math.imul(x + 1, 374761393) ^ Math.imul(y + 1, 668265263);
  value = Math.imul(value ^ (value >>> 13), 1274126177);
  return (value ^ (value >>> 16)) >>> 0;
}

function plot(ctx: CanvasRenderingContext2D, x: number, y: number): void {
  if (x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT) ctx.fillRect(x, y, 1, 1);
}

/** A one-pixel line (canvas lines would be anti-aliased) by Bresenham's method. */
function pixelLine(ctx: CanvasRenderingContext2D, from: { x: number; y: number }, to: { x: number; y: number }): void {
  let x = Math.round(from.x);
  let y = Math.round(from.y);
  const x1 = Math.round(to.x);
  const y1 = Math.round(to.y);
  const dx = Math.abs(x1 - x);
  const dy = -Math.abs(y1 - y);
  const sx = x < x1 ? 1 : -1;
  const sy = y < y1 ? 1 : -1;
  let error = dx + dy;
  for (let guard = 0; guard < 4000; guard++) {
    plot(ctx, x, y);
    if (x === x1 && y === y1) return;
    const doubled = 2 * error;
    if (doubled >= dy) {
      error += dy;
      x += sx;
    }
    if (doubled <= dx) {
      error += dx;
      y += sy;
    }
  }
}

function polyline(ctx: CanvasRenderingContext2D, mode: SideMode, camX: number, points: readonly Pos[], height = 0): void {
  for (let index = 1; index < points.length; index++) {
    const a = points[index - 1];
    const b = points[index];
    if (a === undefined || b === undefined) continue;
    pixelLine(ctx, project(mode, camX, a.x, a.y, height), project(mode, camX, b.x, b.y, height));
  }
}

/** Points on an ellipse measured in metres round (cx, cy), from angle `from` to `to` (radians). */
function arcPoints(cx: number, cy: number, radiusM: number, from: number, to: number, keep: (p: Pos) => boolean): Pos[] {
  const out: Pos[] = [];
  const steps = 48;
  for (let step = 0; step <= steps; step++) {
    const angle = from + ((to - from) * step) / steps;
    const point = { x: cx + (radiusM * Math.cos(angle)) / PITCH_LENGTH_M, y: cy + (radiusM * Math.sin(angle)) / PITCH_WIDTH_M };
    if (keep(point)) out.push(point);
  }
  return out;
}

function drawStands(ctx: CanvasRenderingContext2D, geo: Geometry, camX: number): void {
  const crowdLeft = Math.floor(camX * 900);
  for (let y = 0; y < geo.farY; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const noise = hash(x + crowdLeft, y);
      ctx.fillStyle = noise % 5 === 0 ? (CROWD[noise % CROWD.length] ?? STAND) : STAND;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  // Advertising boards along the far touchline: their colours follow the pitch, so they pan with it.
  const far = geo.ppm * SCALE_FAR * PITCH_LENGTH_M;
  for (let x = 0; x < WIDTH; x++) {
    const metres = (camX + (x - CENTRE_X) / far) * PITCH_LENGTH_M;
    ctx.fillStyle = BOARDS[Math.floor(metres / BOARD_WIDTH_M + 1000) % BOARDS.length] ?? "#ffffff";
    ctx.fillRect(x, geo.farY - BOARD_ROWS, 1, BOARD_ROWS);
  }
}

function drawGrass(ctx: CanvasRenderingContext2D, mode: SideMode, geo: Geometry, camX: number): void {
  for (let row = geo.farY; row < HEIGHT; row++) {
    const y = pitchRowAt(geo, row + 0.5);
    const ppm = geo.ppm * scaleAt(y);
    const length = PITCH_LENGTH_M * ppm;
    ctx.fillStyle = RUN_OFF;
    ctx.fillRect(0, row, WIDTH, 1);
    for (let stripe = 0; stripe < STRIPES; stripe++) {
      const left = CENTRE_X + (stripe / STRIPES - camX) * length;
      const right = CENTRE_X + ((stripe + 1) / STRIPES - camX) * length;
      if (right < 0 || left > WIDTH) continue;
      ctx.fillStyle = stripe % 2 === 0 ? GRASS_LIGHT : GRASS_DARK;
      ctx.fillRect(Math.round(left), row, Math.round(right) - Math.round(left) + 1, 1);
    }
  }
  void mode;
}

function drawMarkings(ctx: CanvasRenderingContext2D, mode: SideMode, camX: number): void {
  ctx.fillStyle = LINE;
  const line = (points: readonly Pos[]): void => polyline(ctx, mode, camX, points);
  line([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }, { x: 0, y: 0 }]);
  line([{ x: 0.5, y: 0 }, { x: 0.5, y: 1 }]);
  line(arcPoints(0.5, 0.5, 9.15, 0, Math.PI * 2, () => true));
  for (const right of [false, true]) {
    const goal = right ? 1 : 0;
    const inward = right ? -1 : 1;
    for (const [depthM, widthM] of [[16.5, 40.3], [5.5, 18.3]] as const) {
      const x = goal + (inward * depthM) / PITCH_LENGTH_M;
      const half = widthM / 2 / PITCH_WIDTH_M;
      line([{ x: goal, y: 0.5 - half }, { x, y: 0.5 - half }, { x, y: 0.5 + half }, { x: goal, y: 0.5 + half }]);
    }
    const spot = goal + (inward * 11) / PITCH_LENGTH_M;
    line([{ x: spot - 0.002, y: 0.5 }, { x: spot + 0.002, y: 0.5 }]);
    const boxEdge = goal + (inward * 16.5) / PITCH_LENGTH_M;
    line(arcPoints(spot, 0.5, 9.15, 0, Math.PI * 2, (p) => (right ? p.x < boxEdge : p.x > boxEdge)));
  }
}

function drawGoals(ctx: CanvasRenderingContext2D, mode: SideMode, camX: number): void {
  const half = 3.66 / PITCH_WIDTH_M;
  for (const goal of [0, 1]) {
    const outward = goal === 0 ? -1 : 1;
    const back = goal + (outward * 2) / PITCH_LENGTH_M;
    const posts = [0.5 - half, 0.5 + half];
    ctx.fillStyle = "#ffffff";
    for (const post of posts) {
      pixelLine(ctx, project(mode, camX, goal, post), project(mode, camX, goal, post, 2.44));
    }
    pixelLine(ctx, project(mode, camX, goal, posts[0] ?? 0.5, 2.44), project(mode, camX, goal, posts[1] ?? 0.5, 2.44));
    ctx.fillStyle = "rgba(255, 255, 255, 0.45)";
    for (const post of posts) {
      pixelLine(ctx, project(mode, camX, goal, post, 2.44), project(mode, camX, back, post, 2.0));
      pixelLine(ctx, project(mode, camX, back, post, 2.0), project(mode, camX, back, post));
    }
    pixelLine(ctx, project(mode, camX, back, posts[0] ?? 0.5, 2.0), project(mode, camX, back, posts[1] ?? 0.5, 2.0));
  }
}

/** Draws the broadcast view of a sample: stands, striped pitch, markings, players and the ball. */
export class SideView {
  private readonly meta: ReplayMeta;
  private readonly kits: Record<TeamSide, Kit>;

  constructor(meta: ReplayMeta) {
    this.meta = meta;
    this.kits = pickKits(meta);
  }

  /** Where a player is on screen in this sample, or null when he is not on the pitch. */
  locate(sample: Sample, mode: SideMode, camX: number, playerId: string): { x: number; y: number } | null {
    const player = sample.players.find((candidate) => candidate.id === playerId);
    if (player === undefined) return null;
    const at = project(mode, camX, player.x, player.y);
    return { x: Math.round(at.x), y: Math.round(at.y) };
  }

  draw(ctx: CanvasRenderingContext2D, sample: Sample | null, extras: Extras, mode: SideMode, camX: number): void {
    const geo = GEOMETRY[mode];
    drawStands(ctx, geo, camX);
    drawGrass(ctx, mode, geo, camX);
    drawMarkings(ctx, mode, camX);
    drawGoals(ctx, mode, camX);
    if (sample === null) return;
    const keepers = this.keeperIds(sample);
    const drawables: { y: number; draw: () => void }[] = [];
    for (const player of sample.players) {
      const side = teamOf(this.meta, player.id);
      const meta = side === null ? undefined : this.meta[side].players[player.id];
      if (side === null || meta === undefined) continue;
      const dress: Dress = { kit: this.kits[side], keeper: keepers.has(player.id) ? KEEPER_COLOURS[side] : null, appearance: meta.appearance };
      const pose = extras.poses.get(player.id);
      const at = project(mode, camX, player.x + (pose?.dx ?? 0) / TOP_DOWN_PPM / PITCH_LENGTH_M, player.y + (pose?.dy ?? 0) / TOP_DOWN_PPM / PITCH_WIDTH_M);
      const x = Math.round(at.x);
      const y = Math.round(at.y);
      const lying = pose !== undefined && (pose.name === "slide" || pose.name === "fall") ? pose.facing : undefined;
      drawables.push({
        y,
        draw: () => {
          if (player.id === extras.focusId) drawFocusMark(ctx, x, y, sizeAt(at.ppm) >= BIG_MARK_FROM);
          drawProfilePlayer(ctx, x, y, dress, {
            facing: pose?.turn === -1 ? flipped(facingOf(player.vx, player.x, sample.ballX)) : facingOf(player.vx, player.x, sample.ballX),
            pose: pose?.profile,
            running: player.running || pose !== undefined,
            phase: extras.t + strideOffset(player.id),
            scale: sizeAt(at.ppm),
            lying,
            arms: pose?.name === "throw",
          });
        },
      });
    }
    this.addReferee(drawables, ctx, extras, mode, camX);
    drawables.push(this.theBall(ctx, sample, extras, mode, camX));
    drawables.sort((a, b) => a.y - b.y);
    for (const item of drawables) item.draw();
  }

  private addReferee(drawables: { y: number; draw: () => void }[], ctx: CanvasRenderingContext2D, extras: Extras, mode: SideMode, camX: number): void {
    const spot = extras.referee;
    if (spot === null) return;
    const at = project(mode, camX, spot.x, spot.y);
    const dress: Dress = { kit: { pattern: "solid", primary: "#d8c04a", secondary: "#14171c" }, keeper: null, appearance: { skin_tone: 3, hair_style: "short", hair_colour: "black", facial_hair: "none", build: "lean" } };
    drawables.push({
      y: Math.round(at.y),
      draw: () => drawProfilePlayer(ctx, Math.round(at.x), Math.round(at.y), dress, { facing: 1, running: true, phase: extras.t, scale: sizeAt(at.ppm) }),
    });
  }

  private theBall(ctx: CanvasRenderingContext2D, sample: Sample, extras: Extras, mode: SideMode, camX: number): { y: number; draw: () => void } {
    const flight = extras.flight;
    if (flight !== null) {
      const point = ballOnFlight(flight, extras.t);
      const ground = project(mode, camX, point.x, point.y);
      const lift = (point.height / TOP_DOWN_PPM) * ground.ppm;
      return {
        y: Math.round(ground.y) + 1,
        draw: () => {
          if (flight.fast) {
            const behind = [0.06, 0.12, 0.18].map((lag) => ballOnFlight(flight, extras.t - lag * (flight.t1 - flight.t0)));
            drawTrail(ctx, behind.map((spot) => {
              const g = project(mode, camX, spot.x, spot.y);
              return { x: Math.round(g.x), y: Math.round(g.y), height: (spot.height / TOP_DOWN_PPM) * g.ppm };
            }));
          }
          drawBall(ctx, Math.round(ground.x), Math.round(ground.y), lift);
        },
      };
    }
    const carried = extras.poses.get(sample.carrierId ?? "");
    const follows = carried?.ballFollows !== false;
    const shiftX = ((follows ? (carried?.dx ?? 0) : 0) + (carried?.ballDx ?? 0)) / TOP_DOWN_PPM / PITCH_LENGTH_M;
    const shiftY = ((follows ? (carried?.dy ?? 0) : 0) + (carried?.ballDy ?? 0)) / TOP_DOWN_PPM / PITCH_WIDTH_M;
    const ground = project(mode, camX, sample.ballX + shiftX, sample.ballY + shiftY);
    const lift = (sample.ballHeight + (carried?.ballLift ?? 0)) / TOP_DOWN_PPM * ground.ppm;
    const carrier = sample.carrierId === null ? null : this.locate(sample, mode, camX, sample.carrierId);
    return {
      y: Math.round(ground.y) + 1,
      draw: () => {
        if (carrier !== null) drawCarrierMark(ctx, carrier.x, carrier.y, sizeAt(ground.ppm) >= BIG_MARK_FROM);
        drawBall(ctx, Math.round(ground.x), Math.round(ground.y), lift);
      },
    };
  }

  private keeperIds(sample: Sample): Set<string> {
    const keepers = new Set<string>();
    const seen = new Set<TeamSide>();
    for (const player of sample.players) {
      const side = teamOf(this.meta, player.id);
      if (side !== null && !seen.has(side)) {
        seen.add(side);
        keepers.add(player.id);
      }
    }
    return keepers;
  }
}

/** A player's stride starts at his own point in the cycle, so a team does not run in lockstep. */
function strideOffset(playerId: string): number {
  let hashed = 0;
  for (const char of playerId) hashed = (hashed * 31 + char.charCodeAt(0)) % 97;
  return (hashed / 97) * 0.36;
}

/** The way a player faces: where he is running, or toward the ball when he is standing. */
function facingOf(vx: number, x: number, ballX: number): 1 | -1 {
  if (Math.abs(vx) > RUN_FACING_MPS) return vx > 0 ? 1 : -1;
  return ballX >= x ? 1 : -1;
}
const RUN_FACING_MPS = 0.6;

function flipped(facing: 1 | -1): 1 | -1 {
  return facing === 1 ? -1 : 1;
}
