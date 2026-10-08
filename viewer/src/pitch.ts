export const WIDTH = 320;
export const HEIGHT = 180;

/** The playing surface in screen pixels; the strip above holds the scoreboard. */
export const PITCH = { x: 10, y: 26, width: 300, height: 148 } as const;

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
const GOAL_DEPTH_PX = 3;
const CIRCLE_RADIUS_PX = 14;

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
function circle(ctx: CanvasRenderingContext2D, centreX: number, centreY: number, radius: number): void {
  let x = radius;
  let y = 0;
  let error = 1 - radius;
  while (x >= y) {
    for (const [dx, dy] of [[x, y], [y, x], [-y, x], [-x, y], [-x, -y], [-y, -x], [y, -x], [x, -y]] as const) {
      rect(ctx, centreX + dx, centreY + dy, 1, 1);
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
  rect(ctx, edge + direction * SPOT_DEPTH * PITCH.width, middle, 1, 1);
  const goalHeight = GOAL_WIDTH * PITCH.height;
  ctx.fillStyle = GOAL_NET;
  outline(ctx, leftEnd ? edge - GOAL_DEPTH_PX : edge, middle - goalHeight / 2, GOAL_DEPTH_PX, goalHeight);
}

/** Draw the backdrop, striped grass and markings. */
export function drawPitch(ctx: CanvasRenderingContext2D): void {
  ctx.fillStyle = BACKDROP;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  const stripe = PITCH.width / STRIPES;
  for (let index = 0; index < STRIPES; index++) {
    ctx.fillStyle = index % 2 === 0 ? GRASS_LIGHT : GRASS_DARK;
    rect(ctx, PITCH.x + index * stripe, PITCH.y, stripe + 1, PITCH.height);
  }
  ctx.fillStyle = LINE;
  outline(ctx, PITCH.x, PITCH.y, PITCH.width, PITCH.height);
  rect(ctx, PITCH.x + PITCH.width / 2, PITCH.y, 1, PITCH.height);
  circle(ctx, PITCH.x + PITCH.width / 2, PITCH.y + PITCH.height / 2, CIRCLE_RADIUS_PX);
  rect(ctx, PITCH.x + PITCH.width / 2 - 1, PITCH.y + PITCH.height / 2 - 1, 3, 3);
  drawEnd(ctx, true);
  drawEnd(ctx, false);
}
