import type { AveragePosition, Grid, PassMapData, PressMapData, ShotDot } from "./analysis.ts";
import type { Pos } from "./events.ts";

/** The analysis maps are drawn smooth at this size, one team attacking left to right. */
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

function place(at: Pos): { x: number; y: number } {
  return { x: PAD + at.x * (MAP_WIDTH - 2 * PAD), y: PAD + at.y * (MAP_HEIGHT - 2 * PAD) };
}

function box(ctx: CanvasRenderingContext2D, fromGoalLine: number, depth: number, width: number, rightEnd: boolean): void {
  const length = MAP_WIDTH - 2 * PAD;
  const height = MAP_HEIGHT - 2 * PAD;
  const w = depth * length;
  const h = width * height;
  const x = rightEnd ? PAD + length - w : PAD + fromGoalLine;
  ctx.strokeRect(x, PAD + (height - h) / 2, w, h);
}

/** The empty pitch every map is drawn on. */
export function drawMapPitch(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, MAP_WIDTH, MAP_HEIGHT);
  ctx.fillStyle = GRASS;
  ctx.fillRect(0, 0, MAP_WIDTH, MAP_HEIGHT);
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
    box(ctx, 0, BOX_DEPTH, BOX_WIDTH, right);
    box(ctx, 0, SIX_DEPTH, SIX_WIDTH, right);
  }
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
  const head = 4 + width;
  ctx.beginPath();
  ctx.moveTo(b.x, b.y);
  ctx.lineTo(b.x - head * Math.cos(angle - 0.45), b.y - head * Math.sin(angle - 0.45));
  ctx.lineTo(b.x - head * Math.cos(angle + 0.45), b.y - head * Math.sin(angle + 0.45));
  ctx.closePath();
  ctx.fill();
}

function label(ctx: CanvasRenderingContext2D, text: string, at: { x: number; y: number }): void {
  ctx.font = "10px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
  ctx.lineWidth = 3;
  ctx.strokeText(text, at.x, at.y);
  ctx.fillText(text, at.x, at.y);
}

const OUTCOME_COLOURS: Record<string, string> = {
  complete: "rgba(255, 255, 255, 0.55)",
  intercepted: "#ff6b6b",
  incomplete: "#ffb347",
  out: "#ffb347",
};

/** Individual passes (complete in white, lost in red or amber, progressive ones brighter). */
export function drawPassLines(ctx: CanvasRenderingContext2D, data: PassMapData): void {
  drawMapPitch(ctx);
  for (const pass of data.lines) {
    const colour = pass.progressive && pass.outcome === "complete" ? "#9be7ff" : (OUTCOME_COLOURS[pass.outcome] ?? "#ffffff");
    arrow(ctx, pass.start, pass.end, colour, 1);
  }
}

/** Players at their average passing position, joined by lines as thick as the passes between them. */
export function drawPassNetwork(ctx: CanvasRenderingContext2D, data: PassMapData, colour: string, nameOf: (id: string) => string): void {
  drawMapPitch(ctx);
  const nodes = new Map(data.nodes.map((node) => [node.id, node]));
  const strongest = Math.max(1, ...data.edges.map((edge) => edge.count));
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
  }
  const busiest = Math.max(1, ...data.nodes.map((node) => node.count));
  for (const node of data.nodes) {
    const at = place(node);
    ctx.fillStyle = colour;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(at.x, at.y, 5 + 6 * (node.count / busiest), 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    label(ctx, nameOf(node.id), { x: at.x, y: at.y - 13 });
  }
}

function drawGrid(ctx: CanvasRenderingContext2D, grid: Grid, rgb: string): void {
  const length = MAP_WIDTH - 2 * PAD;
  const height = MAP_HEIGHT - 2 * PAD;
  grid.cells.forEach((value, index) => {
    if (value <= 0 || grid.max <= 0) return;
    const column = index % grid.columns;
    const row = Math.floor(index / grid.columns);
    ctx.fillStyle = `rgba(${rgb}, ${(0.12 + 0.7 * (value / grid.max)).toFixed(3)})`;
    ctx.fillRect(PAD + (column * length) / grid.columns, PAD + (row * height) / grid.rows, length / grid.columns + 0.5, height / grid.rows + 0.5);
  });
}

/** Time spent per zone, darker where the team (or player) spent more of it. */
export function drawHeatMap(ctx: CanvasRenderingContext2D, grid: Grid): void {
  drawMapPitch(ctx);
  drawGrid(ctx, grid, "255, 214, 64");
  redrawLines(ctx);
}

/** Pressing by zone (where the ball was when the other side had it) and where the ball was won. */
export function drawPressMap(ctx: CanvasRenderingContext2D, data: PressMapData, colour: string): void {
  drawMapPitch(ctx);
  drawGrid(ctx, data.pressure, "255, 120, 64");
  redrawLines(ctx);
  for (const win of data.wins) {
    const at = place(win);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = colour;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(at.x, at.y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
}

const SHOT_COLOURS: Record<string, string> = {
  goal: "#4cd964",
  saved: "#5ac8fa",
  blocked: "#c7a6ff",
  off_target: "#ff6b6b",
  woodwork: "#ffd23f",
};

/** Shots sized by chance quality and coloured by what came of them. */
export function drawShotMap(ctx: CanvasRenderingContext2D, dots: ShotDot[]): void {
  drawMapPitch(ctx);
  for (const dot of dots) {
    const at = place(dot.at);
    ctx.fillStyle = SHOT_COLOURS[dot.outcome] ?? "#ffffff";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(at.x, at.y, 4 + 22 * Math.sqrt(Math.max(dot.xg, 0)), 0, Math.PI * 2);
    ctx.globalAlpha = 0.8;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.stroke();
  }
}

/** Each player at his average position, with the three lines of the team joined up. */
export function drawShape(ctx: CanvasRenderingContext2D, players: AveragePosition[], colour: string, nameOf: (id: string) => string): void {
  drawMapPitch(ctx);
  for (const player of players) {
    const at = place(player);
    ctx.fillStyle = colour;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(at.x, at.y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    label(ctx, nameOf(player.id), { x: at.x, y: at.y - 12 });
  }
}

function redrawLines(ctx: CanvasRenderingContext2D): void {
  ctx.strokeStyle = LINE;
  ctx.lineWidth = 1;
  const length = MAP_WIDTH - 2 * PAD;
  const height = MAP_HEIGHT - 2 * PAD;
  ctx.strokeRect(PAD, PAD, length, height);
  ctx.beginPath();
  ctx.moveTo(PAD + length / 2, PAD);
  ctx.lineTo(PAD + length / 2, PAD + height);
  ctx.stroke();
  for (const right of [false, true]) {
    box(ctx, 0, BOX_DEPTH, BOX_WIDTH, right);
    box(ctx, 0, SIX_DEPTH, SIX_WIDTH, right);
  }
}
