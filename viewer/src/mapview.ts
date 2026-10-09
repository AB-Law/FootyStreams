import type { AveragePosition, Grid, PassMapData, PressMapData, ShotDot } from "./analysis.ts";
import type { Pos } from "./events.ts";

/** The analysis maps are laid out in these units and scaled to the canvas, so they stay sharp. */
export const MAP_WIDTH = 420;
export const MAP_HEIGHT = 272;
const PAD = 10;
const GRASS = "#2f7d32";
const LINE = "rgba(255, 255, 255, 0.55)";
const BOX_DEPTH = 16.5 / 105;
const BOX_WIDTH = 40.3 / 68;
const SIX_DEPTH = 5.5 / 105;
const SIX_WIDTH = 18.3 / 68;
const CIRCLE_M = 9.15;
/** A line is "under the pointer" within this many map units. */
const LINE_REACH = 4;

/** Something on a map the pointer can ask about: it explains itself and may jump the replay. */
export interface Hotspot {
  shape: "circle" | "segment" | "rect";
  x: number;
  y: number;
  /** Radius of a circle, reach of a segment. */
  r?: number;
  x2?: number;
  y2?: number;
  w?: number;
  h?: number;
  text: string;
  /** Replay time to jump to when clicked (a little before the moment). */
  seekTo?: number;
  /** A player this spot stands for: clicking selects him when there is no time to jump to. */
  playerId?: string;
}

/** The first hotspot under a point, preferring small things (dots) over the cells behind them. */
export function hit(hotspots: readonly Hotspot[], x: number, y: number): Hotspot | null {
  let best: Hotspot | null = null;
  let bestRank = Infinity;
  for (const spot of hotspots) {
    const rank = rankOf(spot, x, y);
    if (rank < bestRank) {
      best = spot;
      bestRank = rank;
    }
  }
  return best;
}

/** Smaller is nearer; Infinity when the point misses the hotspot. */
function rankOf(spot: Hotspot, x: number, y: number): number {
  switch (spot.shape) {
    case "circle": {
      const gap = Math.hypot(x - spot.x, y - spot.y);
      return gap <= (spot.r ?? 0) ? gap : Infinity;
    }
    case "segment": {
      const gap = distanceToSegment(x, y, spot);
      return gap <= (spot.r ?? LINE_REACH) ? 100 + gap : Infinity;
    }
    case "rect":
      return x >= spot.x && x <= spot.x + (spot.w ?? 0) && y >= spot.y && y <= spot.y + (spot.h ?? 0) ? 1000 : Infinity;
  }
}

function distanceToSegment(x: number, y: number, spot: Hotspot): number {
  const x2 = spot.x2 ?? spot.x;
  const y2 = spot.y2 ?? spot.y;
  const dx = x2 - spot.x;
  const dy = y2 - spot.y;
  const lengthSquared = dx * dx + dy * dy;
  const along = lengthSquared === 0 ? 0 : Math.min(1, Math.max(0, ((x - spot.x) * dx + (y - spot.y) * dy) / lengthSquared));
  return Math.hypot(x - (spot.x + along * dx), y - (spot.y + along * dy));
}

export function place(at: Pos): { x: number; y: number } {
  return { x: PAD + at.x * (MAP_WIDTH - 2 * PAD), y: PAD + at.y * (MAP_HEIGHT - 2 * PAD) };
}

function box(ctx: CanvasRenderingContext2D, depth: number, width: number, rightEnd: boolean): void {
  const length = MAP_WIDTH - 2 * PAD;
  const height = MAP_HEIGHT - 2 * PAD;
  const w = depth * length;
  const h = width * height;
  ctx.strokeRect(rightEnd ? PAD + length - w : PAD, PAD + (height - h) / 2, w, h);
}

function pitchLines(ctx: CanvasRenderingContext2D): void {
  ctx.strokeStyle = LINE;
  ctx.lineWidth = 1;
  const length = MAP_WIDTH - 2 * PAD;
  const height = MAP_HEIGHT - 2 * PAD;
  ctx.strokeRect(PAD, PAD, length, height);
  ctx.beginPath();
  ctx.moveTo(PAD + length / 2, PAD);
  ctx.lineTo(PAD + length / 2, PAD + height);
  ctx.stroke();
  ctx.beginPath();
  ctx.ellipse(PAD + length / 2, PAD + height / 2, (CIRCLE_M / 105) * length, (CIRCLE_M / 68) * height, 0, 0, Math.PI * 2);
  ctx.stroke();
  for (const right of [false, true]) {
    box(ctx, BOX_DEPTH, BOX_WIDTH, right);
    box(ctx, SIX_DEPTH, SIX_WIDTH, right);
  }
}

/** The empty pitch every map is drawn on. */
export function drawMapPitch(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, MAP_WIDTH, MAP_HEIGHT);
  ctx.fillStyle = GRASS;
  ctx.fillRect(0, 0, MAP_WIDTH, MAP_HEIGHT);
  pitchLines(ctx);
}

/** A small arrow-head line from one point to another. */
function arrow(ctx: CanvasRenderingContext2D, from: Pos, to: Pos, colour: string, width: number): void {
  const a = place(from);
  const b = place(to);
  ctx.strokeStyle = colour;
  ctx.fillStyle = colour;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
  const angle = Math.atan2(b.y - a.y, b.x - a.x);
  const head = 3.5 + width;
  ctx.beginPath();
  ctx.moveTo(b.x, b.y);
  ctx.lineTo(b.x - head * Math.cos(angle - 0.45), b.y - head * Math.sin(angle - 0.45));
  ctx.lineTo(b.x - head * Math.cos(angle + 0.45), b.y - head * Math.sin(angle + 0.45));
  ctx.closePath();
  ctx.fill();
}

function label(ctx: CanvasRenderingContext2D, text: string, at: { x: number; y: number }): void {
  ctx.font = "9px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
  ctx.lineWidth = 2.5;
  ctx.strokeText(text, at.x, at.y);
  ctx.fillText(text, at.x, at.y);
}

function dot(ctx: CanvasRenderingContext2D, at: { x: number; y: number }, radius: number, fill: string, ring: string, ringWidth: number): void {
  ctx.fillStyle = fill;
  ctx.strokeStyle = ring;
  ctx.lineWidth = ringWidth;
  ctx.beginPath();
  ctx.arc(at.x, at.y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

/** What the maps need to describe things in words. */
export interface Words {
  name: (id: string) => string;
  clock: (seconds: number) => string;
}

/** Extra seconds shown before a clicked moment, so the build-up is part of the highlight. */
export const SHOT_LEAD_S = 10;
export const PASS_LEAD_S = 4;
export const WIN_LEAD_S = 5;

const OUTCOME_COLOURS: Record<string, string> = {
  complete: "rgba(255, 255, 255, 0.55)",
  intercepted: "#ff6b6b",
  incomplete: "#ffb347",
  out: "#ffb347",
};
const OUTCOME_WORDS: Record<string, string> = { complete: "complete", intercepted: "intercepted", incomplete: "missed", out: "out of play" };

/** Individual passes (complete in white, lost in red or amber, progressive ones brighter). */
export function drawPassLines(ctx: CanvasRenderingContext2D, data: PassMapData, words: Words): Hotspot[] {
  drawMapPitch(ctx);
  const spots: Hotspot[] = [];
  for (const pass of data.lines) {
    const colour = pass.progressive && pass.outcome === "complete" ? "#9be7ff" : (OUTCOME_COLOURS[pass.outcome] ?? "#ffffff");
    arrow(ctx, pass.start, pass.end, colour, 1);
    const a = place(pass.start);
    const b = place(pass.end);
    const from = pass.fromId === null ? "?" : words.name(pass.fromId);
    const to = pass.toId === null ? "?" : words.name(pass.toId);
    const kind = pass.progressive && pass.outcome === "complete" ? "progressive, " : "";
    spots.push({
      shape: "segment",
      x: a.x,
      y: a.y,
      x2: b.x,
      y2: b.y,
      text: `${from} to ${to}: ${kind}${OUTCOME_WORDS[pass.outcome] ?? pass.outcome}, ${Math.round(pass.lengthM)} m at ${words.clock(pass.t)}. Click to watch.`,
      seekTo: Math.max(0, pass.t - PASS_LEAD_S),
    });
  }
  return spots;
}

/** Players at their average passing position, joined by lines as thick as the passes between them. */
export function drawPassNetwork(ctx: CanvasRenderingContext2D, data: PassMapData, colour: string, words: Words, selectedId: string | null): Hotspot[] {
  drawMapPitch(ctx);
  const nodes = new Map(data.nodes.map((node) => [node.id, node]));
  const strongest = Math.max(1, ...data.edges.map((edge) => edge.count));
  const spots: Hotspot[] = [];
  for (const edge of data.edges) {
    const from = nodes.get(edge.from);
    const to = nodes.get(edge.to);
    if (from === undefined || to === undefined) continue;
    const a = place(from);
    const b = place(to);
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.25 + 0.5 * (edge.count / strongest)})`;
    ctx.lineWidth = 0.5 + 5 * (edge.count / strongest);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    spots.push({ shape: "segment", x: a.x, y: a.y, x2: b.x, y2: b.y, text: `${words.name(edge.from)} to ${words.name(edge.to)}: ${edge.count} completed passes` });
  }
  const busiest = Math.max(1, ...data.nodes.map((node) => node.count));
  for (const node of data.nodes) {
    const at = place(node);
    const radius = 5 + 6 * (node.count / busiest);
    dot(ctx, at, radius, colour, node.id === selectedId ? "#ffd23f" : "#ffffff", node.id === selectedId ? 3 : 1.5);
    label(ctx, words.name(node.id), { x: at.x, y: at.y - radius - 3 });
    const accuracy = node.count === 0 ? 0 : Math.round((100 * node.completed) / node.count);
    spots.push({ shape: "circle", x: at.x, y: at.y, r: radius + 2, text: `${words.name(node.id)}: ${node.count} passes, ${accuracy}% complete. Click to follow him.`, playerId: node.id });
  }
  return spots;
}

function gridRects(grid: Grid): { x: number; y: number; w: number; h: number; index: number }[] {
  const length = MAP_WIDTH - 2 * PAD;
  const height = MAP_HEIGHT - 2 * PAD;
  return grid.cells.map((_, index) => ({
    x: PAD + ((index % grid.columns) * length) / grid.columns,
    y: PAD + (Math.floor(index / grid.columns) * height) / grid.rows,
    w: length / grid.columns,
    h: height / grid.rows,
    index,
  }));
}

function drawGrid(ctx: CanvasRenderingContext2D, grid: Grid, rgb: string): void {
  for (const cell of gridRects(grid)) {
    const value = grid.cells[cell.index] ?? 0;
    if (value <= 0 || grid.max <= 0) continue;
    ctx.fillStyle = `rgba(${rgb}, ${(0.12 + 0.7 * (value / grid.max)).toFixed(3)})`;
    ctx.fillRect(cell.x, cell.y, cell.w + 0.5, cell.h + 0.5);
  }
}

/** Time spent per zone, darker where the team (or player) spent more of it. */
export function drawHeatMap(ctx: CanvasRenderingContext2D, grid: Grid): Hotspot[] {
  drawMapPitch(ctx);
  drawGrid(ctx, grid, "255, 214, 64");
  pitchLines(ctx);
  const total = grid.cells.reduce((sum, value) => sum + value, 0);
  return gridRects(grid).map((cell) => ({
    shape: "rect",
    x: cell.x,
    y: cell.y,
    w: cell.w,
    h: cell.h,
    text: `${total === 0 ? 0 : Math.round((1000 * (grid.cells[cell.index] ?? 0)) / total) / 10}% of the time spent in this zone`,
  }));
}

/** Pressing by zone (where the ball was when the other side had it) and where the ball was won. */
export function drawPressMap(ctx: CanvasRenderingContext2D, data: PressMapData, colour: string, words: Words): Hotspot[] {
  drawMapPitch(ctx);
  drawGrid(ctx, data.pressure, "255, 120, 64");
  pitchLines(ctx);
  const spots: Hotspot[] = gridRects(data.pressure).map((cell) => {
    const samples = data.samples[cell.index] ?? 0;
    const average = data.pressure.cells[cell.index] ?? 0;
    return {
      shape: "rect",
      x: cell.x,
      y: cell.y,
      w: cell.w,
      h: cell.h,
      text: samples === 0 ? "The other side never had the ball here" : `With the ball here the other side held it for ${samples * 2} s; on average ${average.toFixed(1)} of us were within 10 m of it`,
    };
  });
  for (const win of data.wins) {
    const at = place(win.at);
    dot(ctx, at, 4, "#ffffff", colour, 2);
    const who = win.playerId === null ? "A player" : words.name(win.playerId);
    spots.push({ shape: "circle", x: at.x, y: at.y, r: 7, text: `${who} won the ball (${win.how}) at ${words.clock(win.t)}. Click to watch.`, seekTo: Math.max(0, win.t - WIN_LEAD_S) });
  }
  return spots;
}

const SHOT_COLOURS: Record<string, string> = {
  goal: "#4cd964",
  saved: "#5ac8fa",
  blocked: "#c7a6ff",
  off_target: "#ff6b6b",
  woodwork: "#ffd23f",
};
const SHOT_WORDS: Record<string, string> = { goal: "goal", saved: "saved", blocked: "blocked", off_target: "off target", woodwork: "hit the woodwork" };

/** Shots sized by chance quality and coloured by what came of them. */
export function drawShotMap(ctx: CanvasRenderingContext2D, dots: ShotDot[], words: Words): Hotspot[] {
  drawMapPitch(ctx);
  const spots: Hotspot[] = [];
  for (const shot of dots) {
    const at = place(shot.at);
    const radius = 4 + 22 * Math.sqrt(Math.max(shot.xg, 0));
    ctx.globalAlpha = 0.8;
    dot(ctx, at, radius, SHOT_COLOURS[shot.outcome] ?? "#ffffff", "#ffffff", 1);
    ctx.globalAlpha = 1;
    const who = shot.playerId === null ? "A shot" : words.name(shot.playerId);
    spots.push({
      shape: "circle",
      x: at.x,
      y: at.y,
      r: radius,
      text: `${who}, ${words.clock(shot.t)}: ${SHOT_WORDS[shot.outcome] ?? shot.outcome}, xG ${shot.xg.toFixed(2)}. Click to watch.`,
      seekTo: Math.max(0, shot.t - SHOT_LEAD_S),
    });
  }
  return spots;
}

/** Each player at his average position. */
export function drawShape(ctx: CanvasRenderingContext2D, players: AveragePosition[], colour: string, words: Words, selectedId: string | null): Hotspot[] {
  drawMapPitch(ctx);
  const spots: Hotspot[] = [];
  const lined = [...players].sort((a, b) => a.x - b.x);
  for (const player of lined) {
    const at = place(player);
    dot(ctx, at, 7, colour, player.id === selectedId ? "#ffd23f" : "#ffffff", player.id === selectedId ? 3 : 1.5);
    label(ctx, words.name(player.id), { x: at.x, y: at.y - 11 });
    spots.push({ shape: "circle", x: at.x, y: at.y, r: 9, text: `${words.name(player.id)}: average position ${Math.round(player.x * 105)} m from his own goal. Click to follow him.`, playerId: player.id });
  }
  return spots;
}
