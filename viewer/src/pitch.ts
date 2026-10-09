export const WIDTH = 320;
export const HEIGHT = 226;

/**
 * The playing surface in screen pixels; the strip above holds the scoreboard. It keeps the real
 * 105 m x 68 m shape (about 2.86 px per metre both ways), so circles are round and runs are not stretched.
 */
export const PITCH = { x: 10, y: 26, width: 300, height: 194 } as const;

const GRASS_LIGHT = "#3f8f3f";
const GRASS_DARK = "#388538";
const BACKDROP = "#1d2b3a";
const LINE = "#cfe8cf";
const GOAL_NET = "#e8e8e8";
const STRIPES = 12;

// Real proportions, as fractions of the pitch (105 m x 68 m).
const BOX_DEPTH = 16.5 / 105;
const BOX_WIDTH = 40.3 / 68;
const SIX_DEPTH = 5.5 / 105;
const SIX_WIDTH = 18.3 / 68;
const SPOT_DEPTH = 11 / 105;
const GOAL_WIDTH = 7.3 / 68;
const GOAL_DEPTH_PX = 5;
const CIRCLE_RADIUS_M = 9.15;
const PIXELS_PER_METRE = PITCH.width / 105;

export function toScreen(x: number, y: number): { x: number; y: number } {
  return { x: Math.round(PITCH.x + x * PITCH.width), y: Math.round(PITCH.y + y * PITCH.height) };
}

function rect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number): void {
  ctx.fillRect(Math.round(x), Math.round(y), Math.max(Math.round(width), 1), Math.max(Math.round(height), 1));
}

/** Outline of a rectangle, one pixel thick. */
function outline(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number): void {
  rect(ctx, x, y, width, 1);
  rect(ctx, x, y + height - 1, width, 1);
  rect(ctx, x, y, 1, height);
  rect(ctx, x + width - 1, y, 1, height);
}

/** A one-pixel circle by the midpoint algorithm (canvas arcs would be anti-aliased). */
function circle(
  ctx: CanvasRenderingContext2D,
  centreX: number,
  centreY: number,
  radius: number,
  keep: (dx: number, dy: number) => boolean = () => true,
): void {
  let x = radius;
  let y = 0;
  let error = 1 - radius;
  while (x >= y) {
    for (const [dx, dy] of [[x, y], [y, x], [-y, x], [-x, y], [-x, -y], [-y, -x], [y, -x], [x, -y]] as const) {
      if (keep(dx, dy)) rect(ctx, centreX + dx, centreY + dy, 1, 1);
    }
    y++;
    if (error < 0) {
      error += 2 * y + 1;
    } else {
      x--;
      error += 2 * (y - x) + 1;
    }
  }
}

function drawEnd(ctx: CanvasRenderingContext2D, leftEnd: boolean): void {
  const edge = leftEnd ? PITCH.x : PITCH.x + PITCH.width;
  const direction = leftEnd ? 1 : -1;
  const middle = PITCH.y + PITCH.height / 2;
  const box = { depth: BOX_DEPTH * PITCH.width, height: BOX_WIDTH * PITCH.height };
  const six = { depth: SIX_DEPTH * PITCH.width, height: SIX_WIDTH * PITCH.height };
  const place = (depth: number, height: number): [number, number, number, number] => [
    direction > 0 ? edge : edge - depth,
    middle - height / 2,
    depth,
    height,
  ];
  ctx.fillStyle = LINE;
  outline(ctx, ...place(box.depth, box.height));
  outline(ctx, ...place(six.depth, six.height));
  const spotX = edge + direction * SPOT_DEPTH * PITCH.width;
  rect(ctx, spotX, middle, 1, 1);
  // The "D": the part of the 9.15 m circle round the spot that lies outside the box.
  const boxEdge = edge + direction * box.depth;
  circle(ctx, Math.round(spotX), Math.round(middle), Math.round(CIRCLE_RADIUS_M * PIXELS_PER_METRE), (dx) =>
    direction > 0 ? spotX + dx > boxEdge : spotX + dx < boxEdge,
  );
  const goalHeight = GOAL_WIDTH * PITCH.height;
  ctx.fillStyle = GOAL_NET;
  outline(ctx, leftEnd ? edge - GOAL_DEPTH_PX : edge, middle - goalHeight / 2, GOAL_DEPTH_PX, goalHeight);
}

function hash(x: number, y: number): number {
  let value = Math.imul(x + 1, 374761393) ^ Math.imul(y + 1, 668265263);
  value = Math.imul(value ^ (value >>> 13), 1274126177);
  return (value ^ (value >>> 16)) >>> 0;
}

const CROWD = ["#3a2a3f", "#2f3e5e", "#5a2f35", "#6b6f78", "#4d5a3c", "#7a6a3a", "#2b3a4a", "#8a8f98"];
const BOARDS = ["#c8102e", "#0b3d91", "#f2c200", "#e8e8e8", "#006b3c"];
const BOARD_DEPTH = 4;
const FLAG = "#ffd23f";

/** The stands: a dark crowd of speckled colour behind the boards that ring the pitch. */
function drawSurround(ctx: CanvasRenderingContext2D): void {
  for (let y = 0; y < HEIGHT; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const noise = hash(x, y);
      ctx.fillStyle = noise % 5 === 0 ? (CROWD[noise % CROWD.length] ?? BACKDROP) : BACKDROP;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  const left = PITCH.x - BOARD_DEPTH - 1;
  const top = PITCH.y - BOARD_DEPTH - 1;
  const width = PITCH.width + 2 * (BOARD_DEPTH + 1);
  const height = PITCH.height + 2 * (BOARD_DEPTH + 1);
  for (let x = left; x < left + width; x += 1) {
    const colour = BOARDS[Math.floor(x / 24) % BOARDS.length] ?? "#ffffff";
    ctx.fillStyle = colour;
    ctx.fillRect(x, top, 1, BOARD_DEPTH);
    ctx.fillRect(x, top + height - BOARD_DEPTH, 1, BOARD_DEPTH);
  }
  for (let y = top; y < top + height; y += 1) {
    const colour = BOARDS[Math.floor(y / 14) % BOARDS.length] ?? "#ffffff";
    ctx.fillStyle = colour;
    ctx.fillRect(left, y, BOARD_DEPTH, 1);
    ctx.fillRect(left + width - BOARD_DEPTH, y, BOARD_DEPTH, 1);
  }
}

/** Speckle over the grass so large areas are not flat colour. */
function drawGrassTexture(ctx: CanvasRenderingContext2D): void {
  for (let y = PITCH.y; y < PITCH.y + PITCH.height; y++) {
    for (let x = PITCH.x; x < PITCH.x + PITCH.width; x++) {
      const noise = hash(x, y) % 23;
      if (noise === 0) ctx.fillStyle = "rgba(255, 255, 255, 0.07)";
      else if (noise === 1) ctx.fillStyle = "rgba(0, 20, 0, 0.10)";
      else continue;
      ctx.fillRect(x, y, 1, 1);
    }
  }
}

function drawCornerFlags(ctx: CanvasRenderingContext2D): void {
  ctx.fillStyle = LINE;
  const arc = Math.round(PIXELS_PER_METRE);
  for (const [cx, cy] of [
    [PITCH.x, PITCH.y],
    [PITCH.x + PITCH.width - 1, PITCH.y],
    [PITCH.x, PITCH.y + PITCH.height - 1],
    [PITCH.x + PITCH.width - 1, PITCH.y + PITCH.height - 1],
  ] as const) {
    const inside = (dx: number, dy: number): boolean =>
      (cx === PITCH.x ? dx >= 0 : dx <= 0) && (cy === PITCH.y ? dy >= 0 : dy <= 0);
    circle(ctx, cx, cy, arc, inside);
  }
  ctx.fillStyle = FLAG;
  for (const x of [PITCH.x, PITCH.x + PITCH.width - 1]) {
    for (const y of [PITCH.y, PITCH.y + PITCH.height - 1]) ctx.fillRect(x, y - 3, 1, 4);
  }
}

let cached: HTMLCanvasElement | null = null;

function render(): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const ctx = canvas.getContext("2d");
  if (ctx === null) return canvas;
  drawSurround(ctx);
  const stripe = PITCH.width / STRIPES;
  for (let index = 0; index < STRIPES; index++) {
    ctx.fillStyle = index % 2 === 0 ? GRASS_LIGHT : GRASS_DARK;
    rect(ctx, PITCH.x + index * stripe, PITCH.y, stripe + 1, PITCH.height);
  }
  drawGrassTexture(ctx);
  ctx.fillStyle = LINE;
  outline(ctx, PITCH.x, PITCH.y, PITCH.width, PITCH.height);
  rect(ctx, PITCH.x + PITCH.width / 2, PITCH.y, 1, PITCH.height);
  circle(ctx, PITCH.x + PITCH.width / 2, PITCH.y + PITCH.height / 2, Math.round(CIRCLE_RADIUS_M * PIXELS_PER_METRE));
  rect(ctx, PITCH.x + PITCH.width / 2 - 1, PITCH.y + PITCH.height / 2 - 1, 3, 3);
  drawEnd(ctx, true);
  drawEnd(ctx, false);
  drawCornerFlags(ctx);
  return canvas;
}

/** Draw the stands, boards, striped and speckled grass and markings (rendered once, then copied). */
export function drawPitch(ctx: CanvasRenderingContext2D): void {
  cached ??= render();
  ctx.drawImage(cached, 0, 0);
}
