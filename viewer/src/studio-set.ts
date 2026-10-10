import { drawShadowed, textWidth } from "./pixelfont.ts";

// The VPL News studio, 480x270 logical pixels, drawn once into layers that never change: the wall
// behind the anchors and the desk in front of them. Things that move are drawn each frame elsewhere.

export const STUDIO_W = 480;
export const STUDIO_H = 270;
export const DESK_TOP = 196;
const CEILING = 14;
const RAIL = 150;
export const SCREEN_Y = 18;
export const SCREEN_H = 64;
export const LEFT_SCREEN = { x: 14, y: SCREEN_Y, w: 146, h: SCREEN_H } as const;
export const RIGHT_SCREEN = { x: 320, y: SCREEN_Y, w: 146, h: SCREEN_H } as const;
export const WINDOW = { x: 168, y: SCREEN_Y, w: 144, h: SCREEN_H } as const;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function fill(ctx: CanvasRenderingContext2D, colour: string, x: number, y: number, w: number, h: number, alpha = 1): void {
  ctx.globalAlpha = alpha;
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, w, h);
  ctx.globalAlpha = 1;
}

/** A downward cone of light as stacked one-pixel rows, so its edges stay stepped like the rest. */
export function lightCone(ctx: CanvasRenderingContext2D, centre: number, top: number, bottom: number, topWidth: number, bottomWidth: number, colour: string, alpha: number): void {
  for (let y = top; y < bottom; y += 1) {
    const width = Math.round(topWidth + ((bottomWidth - topWidth) * (y - top)) / (bottom - top));
    fill(ctx, colour, Math.round(centre - width / 2), y, width, 1, alpha);
  }
}

function wall(ctx: CanvasRenderingContext2D): void {
  fill(ctx, "#121b27", 0, 0, STUDIO_W, STUDIO_H);
  for (let x = 0; x < STUDIO_W; x += 30) {
    fill(ctx, x % 60 === 0 ? "#17222f" : "#1a2634", x, CEILING, 30, RAIL - CEILING);
    fill(ctx, "#0f1620", x, CEILING, 1, RAIL - CEILING);
  }
  fill(ctx, "#0b1018", 0, 0, STUDIO_W, CEILING);
  fill(ctx, "#223348", 0, CEILING - 1, STUDIO_W, 1);
  fill(ctx, "#2c4058", 0, RAIL, STUDIO_W, 1);
  fill(ctx, "#101923", 0, RAIL + 1, STUDIO_W, DESK_TOP - RAIL);
  for (let x = 0; x < STUDIO_W; x += 40) fill(ctx, "#0c141c", x, RAIL + 1, 1, DESK_TOP - RAIL);
  fill(ctx, "#0a1017", 0, DESK_TOP, STUDIO_W, STUDIO_H - DESK_TOP);
  for (const x of [58, 128, 352, 422]) {
    lightCone(ctx, x + 3, CEILING, 96, 6, 54, "#fff3c4", 0.035);
    fill(ctx, "#fff3c4", x, 9, 7, 2);
    fill(ctx, "#7a6f4a", x, 11, 7, 1);
  }
}

/** A tiny seeded generator, so the skyline is the same every time. */
function sequence(seed: number): () => number {
  let state = seed;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

const SKY = ["#081532", "#0b1d42", "#0f2652", "#142f61", "#1a3a70", "#21467e", "#2a548c", "#34639a"];

/** The window behind the desk: a night sky over a city with a floodlit stadium. */
function skyline(ctx: CanvasRenderingContext2D): void {
  const { x, y, w, h } = WINDOW;
  const next = sequence(7);
  fill(ctx, "#0a1018", x - 2, y - 2, w + 4, h + 4);
  SKY.forEach((colour, band) => fill(ctx, colour, x, y + band * 7, w, 7));
  for (let star = 0; star < 16; star += 1) fill(ctx, star % 3 === 0 ? "#ffffff" : "#9db3d6", x + 4 + Math.floor(next() * (w - 8)), y + 2 + Math.floor(next() * 22), 1, 1);
  fill(ctx, "#f3ecc8", x + 16, y + 9, 9, 9);
  fill(ctx, "#f3ecc8", x + 15, y + 11, 11, 5);
  fill(ctx, "#d6cfa5", x + 19, y + 11, 2, 2);
  fill(ctx, "#d6cfa5", x + 22, y + 15, 2, 1);
  const ground = y + h - 8;
  for (let at = 0; at < w; ) {
    const width = 8 + Math.floor(next() * 12);
    const height = 8 + Math.floor(next() * 22);
    fill(ctx, at % 2 === 0 ? "#0e1626" : "#121d33", x + at, ground - height, width, height);
    for (let row = ground - height + 3; row < ground - 2; row += 4) {
      for (let column = at + 2; column < at + width - 2; column += 4) if (next() < 0.38) fill(ctx, "#ffd866", x + column, row, 2, 2);
    }
    at += width + 1;
  }
  // The stadium: a dark bowl with a bright rim, a glimpse of pitch and four floodlight masts.
  const bowl = x + 52;
  fill(ctx, "#0b1220", bowl, ground - 14, 78, 14);
  fill(ctx, "#2e7d4f", bowl + 8, ground - 12, 62, 3);
  fill(ctx, "#9db3d6", bowl, ground - 14, 78, 1);
  fill(ctx, "#1b2a45", bowl, ground - 13, 78, 1);
  for (const mast of [bowl + 2, bowl + 26, bowl + 50, bowl + 74]) {
    fill(ctx, "#0b1220", mast, ground - 34, 2, 22);
    lightCone(ctx, mast + 1, ground - 32, ground - 14, 5, 26, "#fff6d6", 0.06);
    fill(ctx, "#fff6d6", mast - 2, ground - 36, 6, 3);
    fill(ctx, "#ffffff", mast - 1, ground - 35, 4, 1);
  }
  fill(ctx, "#080d16", x, ground, w, 8);
  for (let at = 4; at < w; at += 9) fill(ctx, at % 18 === 4 ? "#c8102e" : "#ffd866", x + at, ground + 3, 3, 1);
}

/** Everything behind the anchors that never moves. */
export function paintBackdrop(ctx: CanvasRenderingContext2D): void {
  wall(ctx);
  skyline(ctx);
  for (const screen of [LEFT_SCREEN, RIGHT_SCREEN]) {
    fill(ctx, "#05090f", screen.x - 3, screen.y - 3, screen.w + 6, screen.h + 6);
    fill(ctx, "#2a3a4f", screen.x - 2, screen.y - 2, screen.w + 4, 1);
    fill(ctx, "#2a3a4f", screen.x - 2, screen.y - 2, 1, screen.h + 4);
    fill(ctx, "#0b1118", screen.x + 6, screen.y + screen.h + 3, screen.w - 12, 2);
  }
}

/** The desk with the VPL NEWS logo on its front. */
export function paintDesk(ctx: CanvasRenderingContext2D): void {
  fill(ctx, "#8a6048", 20, DESK_TOP, 440, 2);
  fill(ctx, "#6a4a38", 20, DESK_TOP + 2, 440, 5);
  fill(ctx, "#7c5842", 20, DESK_TOP + 4, 440, 1);
  fill(ctx, "#2a1c15", 20, DESK_TOP + 7, 440, 1);
  fill(ctx, "#3b2a21", 28, DESK_TOP + 8, 424, 46);
  for (let x = 28; x < 452; x += 70) fill(ctx, "#2a1d16", x, DESK_TOP + 8, 1, 46);
  fill(ctx, "#2f2018", 28, DESK_TOP + 8, 424, 1);
  fill(ctx, "#3aa6c9", 30, DESK_TOP + 9, 420, 1, 0.9);
  fill(ctx, "#3aa6c9", 30, DESK_TOP + 10, 420, 1, 0.22);
  const logo = textWidth("VPL NEWS", 2);
  const left = Math.floor((STUDIO_W - logo) / 2);
  drawShadowed(ctx, "VPL", left, DESK_TOP + 24, "#f2c200", "#120c08", 2);
  drawShadowed(ctx, "NEWS", left + textWidth("VPL ", 2), DESK_TOP + 24, "#f4f7fb", "#120c08", 2);
  fill(ctx, "#c8102e", left - 8, DESK_TOP + 41, logo + 16, 2);
  fill(ctx, "#f2c200", left - 8, DESK_TOP + 43, logo + 16, 1);
}

/** The tally light on the desk front under an anchor: bright in their colour while they speak. */
export function drawTally(ctx: CanvasRenderingContext2D, centre: number, accent: string, speaking: boolean): void {
  fill(ctx, "#05090f", centre - 15, DESK_TOP + 13, 30, 6);
  fill(ctx, accent, centre - 13, DESK_TOP + 15, 26, 2, speaking ? 1 : 0.28);
  if (speaking) fill(ctx, accent, centre - 15, DESK_TOP + 14, 30, 4, 0.22);
}

/** A table microphone at a seat. */
export function drawMic(ctx: CanvasRenderingContext2D, centre: number): void {
  const x = centre + 17;
  fill(ctx, "#0b0e14", x - 3, DESK_TOP - 1, 8, 2);
  fill(ctx, "#1a1f29", x, DESK_TOP - 7, 1, 7);
  fill(ctx, "#12161d", x - 1, DESK_TOP - 17, 4, 9);
  fill(ctx, "#5a6678", x - 1, DESK_TOP - 17, 1, 8);
  fill(ctx, "#2b3340", x - 1, DESK_TOP - 12, 4, 1);
}

/** Small things on the desk, drawn in front of the anchors: a microphone at each seat, some props. */
export function paintDeskProps(ctx: CanvasRenderingContext2D, seats: number[]): void {
  for (const centre of seats) drawMic(ctx, centre);
  fill(ctx, "#dfe3ea", 36, DESK_TOP - 1, 15, 2);
  fill(ctx, "#b9c0cc", 38, DESK_TOP - 2, 12, 1);
  fill(ctx, "#f4f7fb", 436, DESK_TOP - 8, 7, 8);
  fill(ctx, "#c8102e", 436, DESK_TOP - 5, 7, 1);
  fill(ctx, "#f4f7fb", 443, DESK_TOP - 6, 2, 4);
}
