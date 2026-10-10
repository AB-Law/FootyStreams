import type { Typed } from "./bubble.ts";
import { drawShadowed, drawText, foldText, GLYPH_HEIGHT, LINE_PITCH, textWidth } from "./pixelfont.ts";
import { fill, STUDIO_H, STUDIO_W } from "./studio-set.ts";

// The graphics that sit on top of the picture: the speech bubble over the speaker, the lower third
// naming them, and the ticker along the bottom. All text is the pixel font.

const BORDER = "#14161b";
const CREAM = "#f4ecd8";
const CREAM_LIGHT = "#fffaf0";
const CREAM_DARK = "#dccfb2";
const INK = "#2a2118";
const WHITE = "#f4f7fb";
const GOLD = "#f2c200";
const RED = "#c8102e";
const NAVY = "#0c1a33";

export const BUBBLE_W = 330;
const BUBBLE_PAD = 9;
/** Pixels of text that fit on one bubble line. */
export const TEXT_W = BUBBLE_W - 2 * (2 + BUBBLE_PAD);
/** The bubble's bottom edge; its tail reaches a few pixels lower, to the speaker's head. */
const BUBBLE_BOTTOM = 138;
const TAIL = 6;
const TAIL_MARGIN = 24;

/** Ink that reads on `colour`: dark on light colours, white on dark ones. */
export function inkOn(colour: string): string {
  const value = Number.parseInt(colour.replace("#", ""), 16);
  const luma = 0.299 * ((value >> 16) & 255) + 0.587 * ((value >> 8) & 255) + 0.114 * (value & 255);
  return luma > 150 ? "#14161b" : WHITE;
}

/** A filled rectangle with its four corners cut by `cut` pixels, so the corners step instead of curve. */
function cutRect(ctx: CanvasRenderingContext2D, colour: string, x: number, y: number, w: number, h: number, cut: number): void {
  fill(ctx, colour, x + cut, y, w - 2 * cut, h);
  fill(ctx, colour, x, y + cut, w, h - 2 * cut);
}

export interface BubbleSpec {
  /** Text rows to make room for, so the bubble keeps one size for a whole line of commentary. */
  rows: number;
  /** Where the tail points, as a screen column. */
  tailX: number;
  typed: Typed;
  t: number;
}

export function bubbleHeight(rows: number): number {
  return 4 + 12 + rows * LINE_PITCH - (LINE_PITCH - GLYPH_HEIGHT) + 2;
}

/** Where the bubble sits: centred, unless the speaker is so far to one side that the tail would miss. */
export function bubbleLeft(tailX: number): number {
  const centre = Math.floor((STUDIO_W - BUBBLE_W) / 2);
  const reach = Math.min(Math.max(centre, tailX + TAIL_MARGIN - BUBBLE_W), tailX - TAIL_MARGIN);
  return Math.min(Math.max(reach, 4), STUDIO_W - 4 - BUBBLE_W);
}

export function drawBubble(ctx: CanvasRenderingContext2D, spec: BubbleSpec): void {
  const h = bubbleHeight(spec.rows);
  const x = bubbleLeft(spec.tailX);
  const y = BUBBLE_BOTTOM - h;
  cutRect(ctx, BORDER, x, y, BUBBLE_W, h, 2);
  cutRect(ctx, CREAM, x + 2, y + 2, BUBBLE_W - 4, h - 4, 1);
  fill(ctx, CREAM_LIGHT, x + 4, y + 2, BUBBLE_W - 8, 1);
  fill(ctx, CREAM_DARK, x + 3, y + h - 3, BUBBLE_W - 6, 1);
  const tip = Math.min(Math.max(spec.tailX, x + 18), x + BUBBLE_W - 18);
  for (let step = 0; step <= TAIL; step += 1) {
    const edge = TAIL - step;
    fill(ctx, BORDER, tip - edge, y + h - 2 + step, 2 * edge + 1, 1);
    if (step <= TAIL - 2) fill(ctx, CREAM, tip - (edge - 2), y + h - 2 + step, 2 * (edge - 2) + 1, 1);
  }
  let left = spec.typed.shown;
  spec.typed.lines.forEach((line, row) => {
    const part = line.slice(0, Math.max(0, left));
    left -= line.length;
    if (part !== "") drawText(ctx, part, x + 2 + BUBBLE_PAD, y + 8 + row * LINE_PITCH, INK);
  });
  const more = !spec.typed.speaking && spec.typed.page < spec.typed.pageCount - 1;
  if (more && Math.floor(spec.t * 2) % 2 === 0) {
    const arrow = x + BUBBLE_W - 20;
    fill(ctx, INK, arrow, y + h - 12, 7, 1);
    fill(ctx, INK, arrow + 1, y + h - 11, 5, 1);
    fill(ctx, INK, arrow + 2, y + h - 10, 3, 1);
    fill(ctx, INK, arrow + 3, y + h - 9, 1, 1);
  }
}

/** The name strip at the bottom left. `slide` runs 0 to 1 as it comes in from the edge. */
export function drawLowerThird(ctx: CanvasRenderingContext2D, name: string, topic: string, accent: string, slide: number): void {
  const label = foldText(name).toUpperCase();
  const w = Math.max(124, textWidth(label) + 28);
  const eased = 1 - (1 - slide) * (1 - slide);
  const x = 8 - Math.round((1 - eased) * (w + 16));
  const y = 222;
  fill(ctx, BORDER, x - 1, y - 1, w + 2, 26);
  fill(ctx, accent, x, y, w, 14);
  drawText(ctx, label, x + 8, y + 4, inkOn(accent));
  fill(ctx, NAVY, x, y + 14, w, 10);
  fill(ctx, GOLD, x, y + 14, 3, 10);
  drawText(ctx, foldText(topic).toUpperCase(), x + 8, y + 16, GOLD);
}

const TICKER_TOP = 250;
const TICKER_LEFT = 66;
const TICKER_GAP = 16;
const TICKER_SPEED = 30;

export interface TickerLayout {
  items: { text: string; x: number }[];
  /** Pixels in one full run of the items, after which it repeats. */
  width: number;
}

export function layoutTicker(items: string[]): TickerLayout {
  let x = 0;
  const placed = items.map((item) => {
    const text = foldText(item);
    const at = x;
    x += textWidth(text) + TICKER_GAP * 2 + 3;
    return { text, x: at };
  });
  return { items: placed, width: Math.max(x, 1) };
}

export function drawTicker(ctx: CanvasRenderingContext2D, layout: TickerLayout, t: number): void {
  fill(ctx, GOLD, 0, TICKER_TOP, STUDIO_W, 1);
  fill(ctx, "#0a1428", 0, TICKER_TOP + 1, STUDIO_W, STUDIO_H - TICKER_TOP - 1);
  const shift = Math.floor(t * TICKER_SPEED) % layout.width;
  ctx.save();
  ctx.beginPath();
  ctx.rect(TICKER_LEFT, TICKER_TOP + 1, STUDIO_W - TICKER_LEFT, STUDIO_H - TICKER_TOP);
  ctx.clip();
  for (let run = 0; run < 3; run += 1) {
    for (const item of layout.items) {
      const x = TICKER_LEFT + item.x + run * layout.width - shift;
      if (x > STUDIO_W || x + textWidth(item.text) + TICKER_GAP * 2 < TICKER_LEFT) continue;
      drawText(ctx, item.text, x, TICKER_TOP + 7, WHITE);
      fill(ctx, GOLD, x + textWidth(item.text) + TICKER_GAP, TICKER_TOP + 9, 3, 3);
    }
  }
  ctx.restore();
  fill(ctx, RED, 0, TICKER_TOP + 1, TICKER_LEFT - 1, STUDIO_H - TICKER_TOP - 1);
  fill(ctx, GOLD, TICKER_LEFT - 1, TICKER_TOP + 1, 1, STUDIO_H - TICKER_TOP - 1);
  drawShadowed(ctx, "VPL NEWS", 13, TICKER_TOP + 7, WHITE, "#5a0a16");
}

/** The BREAKING NEWS banner across the lower part of the picture, with the headline scrolling if it is long. */
export function drawBreakingBanner(ctx: CanvasRenderingContext2D, headline: string, clock: number): void {
  const y = 214;
  const lit = Math.floor(clock * 3) % 2 === 0;
  fill(ctx, "#ff2a2a", 0, 0, STUDIO_W, STUDIO_H, lit ? 0.05 : 0);
  fill(ctx, BORDER, 6, y - 1, STUDIO_W - 12, 34);
  fill(ctx, lit ? RED : "#7a0c1c", 7, y, STUDIO_W - 14, 15);
  drawShadowed(ctx, "BREAKING NEWS", 14, y + 4, WHITE, "#3a0610");
  fill(ctx, NAVY, 7, y + 15, STUDIO_W - 14, 17);
  const text = foldText(headline).toUpperCase();
  const room = STUDIO_W - 34;
  ctx.save();
  ctx.beginPath();
  ctx.rect(14, y + 16, room, 15);
  ctx.clip();
  if (textWidth(text) <= room) drawText(ctx, text, 14, y + 20, WHITE);
  else {
    const loop = textWidth(text) + 40;
    const shift = Math.floor(clock * 36) % loop;
    drawText(ctx, text, 14 - shift, y + 20, WHITE);
    drawText(ctx, text, 14 - shift + loop, y + 20, WHITE);
  }
  ctx.restore();
}
