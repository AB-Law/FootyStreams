import type { Pos } from "./events.ts";
import { ballOnFlight } from "./flights.ts";
import { FEET_X, FEET_Y, FIGURE_H, FIGURE_HEIGHT_PX, FIGURE_W, figureFromJoints, figureSprite, gaitFor, type FigureDress } from "./figure.ts";
import { sampleAt, type Sample } from "./interpolate.ts";
import { teamOf, type ReplayMeta, type TeamSide } from "./meta.ts";
import { KEEPER_COLOURS, pickKits, type Kit } from "./palette.ts";
import type { Extras } from "./scene.ts";
import type { SceneFrame } from "./sceneplay.ts";
import type { Frame } from "./store.ts";

/**
 * The broadcast view: the pitch seen from a gantry on the touchline, far side up and near side down,
 * drawn at twice the resolution of the rest of the page so the players have faces and kit.
 *
 * World coordinates are the pitch's own (x along its length, y across it, both 0..1, plus a height in
 * metres). Depth gives scale: the far touchline is drawn about three quarters the size of the near
 * one, and rows are spaced the way a real camera spaces them, so the pitch is a trapezoid. The
 * camera pans along the pitch only.
 */
export type SideMode = "wide" | "broadcast";
/** Who wears a name tag: the player on the ball and the one being followed, everybody, or nobody. */
export type NameMode = "carrier" | "all" | "off";

export const NAME_MODES: readonly NameMode[] = ["carrier", "all", "off"];

/** The canvas the view draws on: twice the pixels of the page's logical 320 x 226 screen. */
export const SIDE_WIDTH = 640;
export const SIDE_HEIGHT = 452;

interface Geometry {
  /** Screen row of the far and near touchline. */
  farY: number;
  nearY: number;
  /** Pixels per metre along the near touchline. */
  ppm: number;
}

const GEOMETRY: Record<SideMode, Geometry> = {
  wide: { farY: 250, nearY: 420, ppm: 5.9 },
  broadcast: { farY: 150, nearY: 436, ppm: 15.5 },
};

const SCALE_FAR = 0.74;
const SCALE_NEAR = 1;
const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;
const CENTRE_X = SIDE_WIDTH / 2;
/** The top-down view's pixels per metre, which flight heights are measured in. */
const TOP_DOWN_PPM = 300 / PITCH_LENGTH_M;
/** Grid pixels in a figure to a metre: a sprite is drawn at `ppm / this` times its grid size. */
const FIGURE_PX_PER_M = FIGURE_HEIGHT_PX / 1.8;
/** Nobody is drawn smaller than this (the wide shot): below it there are too few pixels to read. */
const MIN_SPRITE_SCALE = 0.42;
/** Sprites drawn smaller than this are smoothed as they shrink, as sharp sampling would drop pixels. */
const SHARP_FROM_SCALE = 0.85;
/** The camera follows the ball as it was over this many seconds, so it glides. */
const FOLLOW_SECONDS = 1.5;
const FOLLOW_SAMPLES = 4;
const RUN_FACING_MPS = 0.6;
const STRIDE_CYCLE_S = 0.36;

const GRASS_LIGHT = "#3f8f3f";
const GRASS_DARK = "#388538";
const RUN_OFF = "#2f7433";
const LINE = "#dcefdc";
const STAND = "#1d2b3a";
const CROWD = ["#3a2a3f", "#2f3e5e", "#5a2f35", "#6b6f78", "#4d5a3c", "#7a6a3a", "#2b3a4a", "#8a8f98"];
const BOARDS = ["#c8102e", "#0b3d91", "#f2c200", "#e8e8e8", "#006b3c"];
const STRIPES = 10;
const BOARD_ROWS = 14;
const BOARD_WIDTH_M = 4.2;
/** The stands are painted once for this span of the pitch (fractions of its length) behind the far touchline. */
const STANDS_FROM = -0.35;
const STANDS_TO = 1.35;
const CROWD_BLOCK_PX = 2;
const REFEREE_KIT: Kit = { pattern: "solid", primary: "#101114", secondary: "#f2d230" };
const REFEREE_LOOK = { skin_tone: 3, hair_style: "short", hair_colour: "black", facial_hair: "none", build: "lean" };
const TAG_TEXT = "#ffffff";
const TAG_CARRIER = "#ffe45c";
const FOCUS_COLOUR = "#4cd9ff";

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
  const ppm = geo.ppm * scaleAt(y);
  const ground = geo.farY + (geo.nearY - geo.farY) * depth(y);
  return { x: CENTRE_X + (x - camX) * PITCH_LENGTH_M * ppm, y: ground - heightM * ppm, ppm };
}

/** The pan limits: the camera keeps the goal lines near the edge of the screen at most. */
function panRange(mode: SideMode): { low: number; high: number } {
  if (mode === "wide") return { low: 0.5, high: 0.5 };
  const half = SIDE_WIDTH / 2 / (GEOMETRY.broadcast.ppm * PITCH_LENGTH_M * SCALE_NEAR);
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

/** The pixel size of a marking: two, as the canvas is twice the page's own resolution. */
const LINE_PX = 2;

function plot(ctx: CanvasRenderingContext2D, x: number, y: number): void {
  if (x >= -LINE_PX && x < SIDE_WIDTH && y >= -LINE_PX && y < SIDE_HEIGHT) ctx.fillRect(x, y, LINE_PX, LINE_PX);
}

/** A hard-edged line (canvas lines would be anti-aliased) by Bresenham's method. */
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
  for (let guard = 0; guard < 6000; guard++) {
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

function polyline(ctx: CanvasRenderingContext2D, mode: SideMode, camX: number, points: readonly Pos[]): void {
  for (let index = 1; index < points.length; index++) {
    const a = points[index - 1];
    const b = points[index];
    if (a === undefined || b === undefined) continue;
    pixelLine(ctx, project(mode, camX, a.x, a.y), project(mode, camX, b.x, b.y));
  }
}

/** Points on an ellipse measured in metres round (cx, cy), from angle `from` to `to` (radians). */
function arcPoints(cx: number, cy: number, radiusM: number, from: number, to: number, keep: (p: Pos) => boolean): Pos[] {
  const out: Pos[] = [];
  const steps = 64;
  for (let step = 0; step <= steps; step++) {
    const angle = from + ((to - from) * step) / steps;
    const point = { x: cx + (radiusM * Math.cos(angle)) / PITCH_LENGTH_M, y: cy + (radiusM * Math.sin(angle)) / PITCH_WIDTH_M };
    if (keep(point)) out.push(point);
  }
  return out;
}

const standsCache = new Map<SideMode, HTMLCanvasElement>();

/** The crowd and the advertising boards along the far touchline, painted once for the whole length of the pitch. */
function stands(mode: SideMode): HTMLCanvasElement {
  const found = standsCache.get(mode);
  if (found !== undefined) return found;
  const geo = GEOMETRY[mode];
  const farPpm = geo.ppm * SCALE_FAR;
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil((STANDS_TO - STANDS_FROM) * PITCH_LENGTH_M * farPpm);
  canvas.height = geo.farY;
  const ctx = canvas.getContext("2d");
  if (ctx === null) return canvas;
  const crowdRows = geo.farY - BOARD_ROWS;
  for (let y = 0; y < crowdRows; y += CROWD_BLOCK_PX) {
    for (let x = 0; x < canvas.width; x += CROWD_BLOCK_PX) {
      const noise = hash(x / CROWD_BLOCK_PX, y / CROWD_BLOCK_PX);
      ctx.fillStyle = noise % 4 === 0 ? (CROWD[noise % CROWD.length] ?? STAND) : STAND;
      ctx.fillRect(x, y, CROWD_BLOCK_PX, CROWD_BLOCK_PX);
    }
  }
  // The back of the stand falls into shadow.
  const shadow = ctx.createLinearGradient(0, 0, 0, crowdRows);
  shadow.addColorStop(0, "rgba(5, 8, 12, 0.7)");
  shadow.addColorStop(1, "rgba(5, 8, 12, 0)");
  ctx.fillStyle = shadow;
  ctx.fillRect(0, 0, canvas.width, crowdRows);
  for (let x = 0; x < canvas.width; x++) {
    const metres = x / farPpm;
    ctx.fillStyle = BOARDS[Math.floor(metres / BOARD_WIDTH_M) % BOARDS.length] ?? "#ffffff";
    ctx.fillRect(x, crowdRows, 1, BOARD_ROWS);
  }
  standsCache.set(mode, canvas);
  return canvas;
}

function drawStands(ctx: CanvasRenderingContext2D, mode: SideMode, geo: Geometry, camX: number): void {
  const farPpm = geo.ppm * SCALE_FAR;
  const canvas = stands(mode);
  const left = Math.round((camX - STANDS_FROM) * PITCH_LENGTH_M * farPpm - CENTRE_X);
  const from = Math.min(Math.max(left, 0), Math.max(canvas.width - SIDE_WIDTH, 0));
  ctx.drawImage(canvas, from, 0, SIDE_WIDTH, geo.farY, 0, 0, SIDE_WIDTH, geo.farY);
}

function drawGrass(ctx: CanvasRenderingContext2D, geo: Geometry, camX: number): void {
  for (let row = geo.farY; row < SIDE_HEIGHT; row++) {
    const y = pitchRowAt(geo, row + 0.5);
    const length = PITCH_LENGTH_M * geo.ppm * scaleAt(y);
    ctx.fillStyle = RUN_OFF;
    ctx.fillRect(0, row, SIDE_WIDTH, 1);
    for (let stripe = 0; stripe < STRIPES; stripe++) {
      const left = CENTRE_X + (stripe / STRIPES - camX) * length;
      const right = CENTRE_X + ((stripe + 1) / STRIPES - camX) * length;
      if (right < 0 || left > SIDE_WIDTH) continue;
      ctx.fillStyle = stripe % 2 === 0 ? GRASS_LIGHT : GRASS_DARK;
      ctx.fillRect(Math.round(left), row, Math.round(right) - Math.round(left) + 1, 1);
    }
  }
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
    for (const post of posts) pixelLine(ctx, project(mode, camX, goal, post), project(mode, camX, goal, post, 2.44));
    pixelLine(ctx, project(mode, camX, goal, posts[0] ?? 0.5, 2.44), project(mode, camX, goal, posts[1] ?? 0.5, 2.44));
    ctx.fillStyle = "rgba(255, 255, 255, 0.45)";
    for (const post of posts) {
      pixelLine(ctx, project(mode, camX, goal, post, 2.44), project(mode, camX, back, post, 2.0));
      pixelLine(ctx, project(mode, camX, back, post, 2.0), project(mode, camX, back, post));
    }
    pixelLine(ctx, project(mode, camX, back, posts[0] ?? 0.5, 2.0), project(mode, camX, back, posts[1] ?? 0.5, 2.0));
  }
}

/** A player's stride starts at his own point in the cycle, so a team does not run in lockstep. */
function strideOffset(playerId: string): number {
  let hashed = 0;
  for (const char of playerId) hashed = (hashed * 31 + char.charCodeAt(0)) % 97;
  return (hashed / 97) * STRIDE_CYCLE_S;
}

/** The way a player faces: where he is running, or toward the ball when he is standing. */
function facingOf(vx: number, x: number, ballX: number): 1 | -1 {
  if (Math.abs(vx) > RUN_FACING_MPS) return vx > 0 ? 1 : -1;
  return ballX >= x ? 1 : -1;
}

/** The last word of a name, which is what a tag shows. */
function surname(name: string): string {
  const parts = name.split(" ");
  return parts[parts.length - 1] ?? name;
}

interface Drawable {
  y: number;
  draw: () => void;
}

interface Tag {
  x: number;
  y: number;
  text: string;
  carrier: boolean;
}

/** Draws the broadcast view of a sample: stands, striped pitch, markings, players and the ball. */
export class SideView {
  private readonly meta: ReplayMeta;
  private readonly kits: Record<TeamSide, Kit>;

  constructor(meta: ReplayMeta) {
    this.meta = meta;
    this.kits = pickKits(meta);
  }

  /** Where a player's feet are on screen in this sample (canvas pixels), or null when he is not on the pitch. */
  locate(sample: Sample, mode: SideMode, camX: number, playerId: string): { x: number; y: number } | null {
    const player = sample.players.find((candidate) => candidate.id === playerId);
    if (player === undefined) return null;
    const at = project(mode, camX, player.x, player.y);
    return { x: Math.round(at.x), y: Math.round(at.y) };
  }

  private spriteScale(ppm: number): number {
    return Math.max(ppm / FIGURE_PX_PER_M, MIN_SPRITE_SCALE);
  }

  draw(ctx: CanvasRenderingContext2D, sample: Sample | null, extras: Extras, mode: SideMode, camX: number, scene: SceneFrame, names: NameMode): void {
    const geo = GEOMETRY[mode];
    ctx.imageSmoothingEnabled = false;
    drawStands(ctx, mode, geo, camX);
    drawGrass(ctx, geo, camX);
    drawMarkings(ctx, mode, camX);
    drawGoals(ctx, mode, camX);
    if (sample === null) return;
    const keepers = this.keeperIds(sample);
    const drawables: Drawable[] = [];
    const tags: Tag[] = [];
    // The player on the ball wears the carrier's tag only while he has it, not while a pass is in the air.
    const carrierId = extras.flight === null && scene.ball === null ? sample.carrierId : null;
    for (const player of sample.players) {
      const side = teamOf(this.meta, player.id);
      const meta = side === null ? undefined : this.meta[side].players[player.id];
      if (side === null || meta === undefined) continue;
      const dress: FigureDress = { kit: this.kits[side], keeper: keepers.has(player.id) ? KEEPER_COLOURS[side] : null, appearance: meta.appearance };
      const posed = scene.poses.get(player.id);
      const worldX = player.x + (posed?.dxM ?? 0) / PITCH_LENGTH_M;
      const worldY = player.y + (posed?.dyM ?? 0) / PITCH_WIDTH_M;
      const ground = project(mode, camX, worldX, worldY);
      const lift = (posed?.h ?? 0) * ground.ppm;
      const gait = gaitFor(Math.hypot(player.vx, player.vy));
      const sprite = posed !== undefined ? figureFromJoints(dress, posed.joints) : figureSprite(dress, gait.pose, (extras.t + strideOffset(player.id)) / gait.period, gait.amp);
      const facing = posed?.facing ?? facingOf(player.vx, player.x, sample.ballX);
      const scale = this.spriteScale(ground.ppm);
      const x = Math.round(ground.x);
      const y = Math.round(ground.y);
      const isCarrier = carrierId === player.id;
      drawables.push({
        y,
        draw: () => {
          this.drawShadow(ctx, x, y, scale, posed?.h ?? 0);
          if (player.id === extras.focusId) this.drawFocus(ctx, x, y, scale);
          this.drawFigure(ctx, sprite, x, Math.round(y - lift), scale, facing, posed?.lying ?? null);
        },
      });
      const wanted = names === "all" || (names === "carrier" && (isCarrier || player.id === extras.focusId));
      if (wanted) {
        const head = Math.round(y - lift - FIGURE_HEIGHT_PX * scale - 8);
        const down = posed !== undefined && posed.lying !== null;
        tags.push({ x, y: down ? Math.round(y - 14 * scale) : head, text: `${meta.number ?? ""} ${surname(meta.name)}`.trim(), carrier: isCarrier });
      }
    }
    this.addReferee(drawables, ctx, extras, mode, camX);
    drawables.push(this.theBall(ctx, sample, extras, mode, camX, scene));
    drawables.sort((a, b) => a.y - b.y).forEach((item) => item.draw());
    // Carrier last, so its tag is never hidden under a neighbour's.
    tags.sort((a, b) => Number(a.carrier) - Number(b.carrier)).forEach((tag) => this.drawTag(ctx, tag));
  }

  private drawShadow(ctx: CanvasRenderingContext2D, x: number, y: number, scale: number, height: number): void {
    const spread = Math.max(0.5, 1 - height * 0.25);
    ctx.fillStyle = `rgba(0, 0, 0, ${(0.3 * spread).toFixed(2)})`;
    ctx.beginPath();
    ctx.ellipse(x, y + 1, 11 * scale * spread, 3.4 * scale * spread, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  /** The ring and arrow marking the player the camera follows. */
  private drawFocus(ctx: CanvasRenderingContext2D, x: number, y: number, scale: number): void {
    ctx.strokeStyle = FOCUS_COLOUR;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(x, y + 1, 15 * scale, 5 * scale, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  /**
   * Draw a figure with its feet at (x, y), facing right or left, upright or lying. A figure is a
   * small sprite scaled up to the depth it stands at; sharp sampling keeps the pixels crisp when it
   * is large, and smoothing keeps the thin lines when it is shrunk far.
   */
  private drawFigure(ctx: CanvasRenderingContext2D, sprite: HTMLCanvasElement, x: number, y: number, scale: number, facing: 1 | -1, lying: "forward" | "slide" | null): void {
    ctx.save();
    ctx.imageSmoothingEnabled = scale < SHARP_FROM_SCALE;
    ctx.imageSmoothingQuality = "high";
    ctx.translate(x, y);
    if (lying !== null) ctx.translate(0, -5 * scale);
    if (facing < 0) ctx.scale(-1, 1);
    if (lying === "forward") ctx.rotate(Math.PI / 2);
    if (lying === "slide") ctx.rotate(-Math.PI / 2);
    ctx.drawImage(sprite, -FEET_X * scale, -FEET_Y * scale, FIGURE_W * scale, FIGURE_H * scale);
    ctx.restore();
  }

  /** A name tag: shirt number and surname above a player's head, gold with a pointer for the one on the ball. */
  private drawTag(ctx: CanvasRenderingContext2D, tag: Tag): void {
    ctx.save();
    ctx.font = `bold ${tag.carrier ? 14 : 12}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.lineJoin = "round";
    ctx.lineWidth = 4;
    ctx.strokeStyle = "rgba(8, 12, 18, 0.85)";
    ctx.strokeText(tag.text, tag.x, tag.y);
    ctx.fillStyle = tag.carrier ? TAG_CARRIER : TAG_TEXT;
    ctx.fillText(tag.text, tag.x, tag.y);
    if (tag.carrier) {
      ctx.beginPath();
      ctx.moveTo(tag.x - 4, tag.y + 4);
      ctx.lineTo(tag.x + 4, tag.y + 4);
      ctx.lineTo(tag.x, tag.y + 10);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  private addReferee(drawables: Drawable[], ctx: CanvasRenderingContext2D, extras: Extras, mode: SideMode, camX: number): void {
    const spot = extras.referee;
    if (spot === null) return;
    const at = project(mode, camX, spot.x, spot.y);
    const dress: FigureDress = { kit: REFEREE_KIT, keeper: null, appearance: REFEREE_LOOK };
    const scale = this.spriteScale(at.ppm);
    const x = Math.round(at.x);
    const y = Math.round(at.y);
    const sprite = figureSprite(dress, "run", extras.t / 0.6, 0.7);
    drawables.push({
      y,
      draw: () => {
        this.drawShadow(ctx, x, y, scale, 0);
        this.drawFigure(ctx, sprite, x, y, scale, 1, null);
        if (extras.whistle) this.drawTag(ctx, { x, y: Math.round(y - (FIGURE_HEIGHT_PX + 6) * scale), text: "!", carrier: true });
      },
    });
  }

  /** The ball's place in world terms: a scene's, a flight's or the replay's own (heights in metres). */
  private ballPlace(sample: Sample, extras: Extras, scene: SceneFrame): { x: number; y: number; h: number } {
    if (scene.ball !== null) return scene.ball;
    if (extras.flight !== null) {
      const point = ballOnFlight(extras.flight, extras.t);
      return { x: point.x, y: point.y, h: point.height / TOP_DOWN_PPM };
    }
    return { x: sample.ballX, y: sample.ballY, h: sample.ballHeight / TOP_DOWN_PPM };
  }

  private theBall(ctx: CanvasRenderingContext2D, sample: Sample, extras: Extras, mode: SideMode, camX: number, scene: SceneFrame): Drawable {
    const placed = this.ballPlace(sample, extras, scene);
    const ground = project(mode, camX, placed.x, placed.y);
    const lift = placed.h * ground.ppm;
    const radius = Math.max(2.6, 0.2 * ground.ppm);
    const flight = scene.ball === null ? extras.flight : null;
    return {
      y: Math.round(ground.y) + 1,
      draw: () => {
        if (flight !== null && flight.fast) {
          for (const lag of [0.06, 0.12, 0.18]) {
            const behind = ballOnFlight(flight, extras.t - lag * (flight.t1 - flight.t0));
            const trail = project(mode, camX, behind.x, behind.y);
            ctx.fillStyle = `rgba(255, 255, 255, ${(0.5 - lag * 2).toFixed(2)})`;
            ctx.beginPath();
            ctx.arc(Math.round(trail.x), Math.round(trail.y - (behind.height / TOP_DOWN_PPM) * trail.ppm - radius), radius * 0.8, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        const x = Math.round(ground.x);
        const y = Math.round(ground.y);
        const squash = Math.max(0.45, 1 - lift * 0.01);
        ctx.fillStyle = `rgba(0, 0, 0, ${(0.32 * squash).toFixed(2)})`;
        ctx.beginPath();
        ctx.ellipse(x, y + 1, radius * 1.5 * squash, radius * 0.5 * squash, 0, 0, Math.PI * 2);
        ctx.fill();
        const top = y - radius - lift;
        ctx.fillStyle = "#10141a";
        ctx.beginPath();
        ctx.arc(x, top, radius + 1, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(x, top, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#2a2e36";
        const patch = Math.max(2, Math.round(radius * 0.7));
        ctx.fillRect(Math.round(x - radius * 0.3), Math.round(top - radius * 0.45), patch, patch);
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
