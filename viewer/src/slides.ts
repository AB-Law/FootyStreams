import type { Slide } from "./commentary.ts";
import { clipText, drawShadowed, drawText, foldText, textWidth, wrapText } from "./pixelfont.ts";
import { fill, STUDIO_H, STUDIO_W } from "./studio-set.ts";

// The cards of a break: sponsor ads, the table, the latest results, what is on next, and the
// BREAKING NEWS flash. They fill the whole picture above the ticker, and are pure functions of the
// time, like the rest of the studio.

/** Rows of picture above the ticker. */
const FIELD_H = 250;
const WIPE_SECONDS = 0.45;
const WHITE = "#f4f7fb";
const GOLD = "#f2c200";
const INK = "#101418";
const BLUE = "#0d3b8c";
const BLUE_DARK = "#0a2c6b";
const FLASH_A = "#c8102e";
const FLASH_B = "#7a0c1c";

export function slidesDuration(slides: Slide[]): number {
  return slides.reduce((sum, slide) => sum + slide.seconds, 0);
}

/** Which slide is up at `t` and how far into it: past the end, the last slide. */
export function slideAt(slides: Slide[], t: number): { index: number; local: number } {
  let start = 0;
  for (let index = 0; index < slides.length; index += 1) {
    const end = start + (slides[index]?.seconds ?? 0);
    if (t < end) return { index, local: t - start };
    start = end;
  }
  const last = Math.max(slides.length - 1, 0);
  return { index: last, local: slides[last]?.seconds ?? 0 };
}

/** The largest of 4, 3, 2, 1 at which `text` fits in `room` pixels. */
export function fitScale(text: string, room: number, top = 4): number {
  for (let scale = top; scale > 1; scale -= 1) if (textWidth(text, scale) <= room) return scale;
  return 1;
}

/** Ink for text on `colour`: dark on light colours, white on dark ones. */
function inkOn(colour: string): string {
  const value = Number.parseInt(colour.replace("#", ""), 16);
  const luma = 0.299 * ((value >> 16) & 255) + 0.587 * ((value >> 8) & 255) + 0.114 * (value & 255);
  return luma > 150 ? INK : WHITE;
}

function centred(ctx: CanvasRenderingContext2D, text: string, y: number, colour: string, scale: number, shadow?: string): void {
  const x = Math.floor((STUDIO_W - textWidth(text, scale)) / 2);
  if (shadow === undefined) drawText(ctx, text, x, y, colour, scale);
  else drawShadowed(ctx, text, x, y, colour, shadow, scale);
}

function frame(ctx: CanvasRenderingContext2D, colour: string, local: number): void {
  const wipe = Math.min(1, local / WIPE_SECONDS);
  const width = Math.round(STUDIO_W * (1 - (1 - wipe) * (1 - wipe)));
  fill(ctx, colour, 0, 0, width, FIELD_H);
  if (width < STUDIO_W) fill(ctx, GOLD, width, 0, 3, FIELD_H);
}

function stripes(ctx: CanvasRenderingContext2D, colour: string, clock: number): void {
  const shift = Math.floor(clock * 12) % 24;
  for (let x = -FIELD_H; x < STUDIO_W; x += 24) {
    for (let y = 0; y < FIELD_H; y += 2) {
      const left = Math.max(x + y + shift, 0);
      const right = Math.min(x + y + shift + 6, STUDIO_W);
      if (right > left) fill(ctx, colour, left, y, right - left, 2, 0.07);
    }
  }
}

function ad(ctx: CanvasRenderingContext2D, slide: Slide, local: number, clock: number): void {
  frame(ctx, slide.dark, local);
  stripes(ctx, slide.accent, clock);
  const panel = { x: 50, y: 38, w: 380, h: 158 };
  fill(ctx, "#05090f", panel.x - 3, panel.y - 3, panel.w + 6, panel.h + 6);
  fill(ctx, slide.accent, panel.x, panel.y, panel.w, panel.h);
  const ink = inkOn(slide.accent);
  const brand = foldText(slide.title).toUpperCase();
  const scale = fitScale(brand, panel.w - 24);
  const lines = scale === 1 ? wrapText(brand, panel.w - 24, 2) : [brand];
  const size = scale === 1 ? 2 : scale;
  const top = panel.y + 26 + (lines.length > 1 ? 0 : 10);
  lines.forEach((line, row) => centred(ctx, line, top + row * (size * 8 + 2), ink, size));
  const slogan = wrapText(slide.lines[0] ?? "", panel.w - 40, 1).slice(0, 2);
  slogan.forEach((line, row) => centred(ctx, line, panel.y + 112 + row * 11, ink, 1));
  fill(ctx, ink, panel.x, panel.y + panel.h - 8, panel.w, 8, 0.18);
  for (let x = panel.x + 6; x < panel.x + panel.w - 6; x += 16) fill(ctx, ink, x, panel.y + panel.h - 5, 8, 2, 0.5);
  fill(ctx, "#05090f", panel.x - 3, panel.y - 12, 62, 12);
  drawText(ctx, "ADVERT", panel.x + 4, panel.y - 9, GOLD);
}

function heading(ctx: CanvasRenderingContext2D, title: string, scale: number): void {
  fill(ctx, GOLD, 0, 24, STUDIO_W, 3);
  centred(ctx, foldText(title).toUpperCase(), 36, WHITE, scale, INK);
  fill(ctx, GOLD, 0, 36 + scale * 7 + 8, STUDIO_W, 3);
}

function board(ctx: CanvasRenderingContext2D, slide: Slide, local: number, clock: number): void {
  frame(ctx, BLUE, local);
  stripes(ctx, WHITE, clock);
  heading(ctx, slide.title, 3);
  const rows = slide.rows.length > 0 ? slide.rows.map((row) => ({ left: row.label, right: row.value ?? "" })) : slide.lines.map((line) => ({ left: line, right: "" }));
  rows.slice(0, 6).forEach((row, index) => {
    const y = 76 + index * 26;
    if (index % 2 === 0) fill(ctx, BLUE_DARK, 40, y - 4, 400, 24);
    const right = foldText(row.right).toUpperCase();
    const room = 400 - 50 - (right === "" ? 0 : textWidth(right, 2) + 16);
    const left = clipText(row.left, room, 2).toUpperCase();
    const scale = slide.rows.length === 0 ? fitScale(left, 380, 2) : 2;
    if (slide.rows.length > 0) drawShadowed(ctx, String(index + 1), 48, y, GOLD, INK, 2);
    drawShadowed(ctx, left, slide.rows.length > 0 ? 72 : 52, y, WHITE, INK, scale);
    if (right !== "") drawShadowed(ctx, right, 432 - textWidth(right, 2), y, GOLD, INK, 2);
  });
}

function fixture(ctx: CanvasRenderingContext2D, slide: Slide, local: number, clock: number): void {
  frame(ctx, "#12304f", local);
  stripes(ctx, GOLD, clock);
  heading(ctx, slide.title, 3);
  const [home = "", versus = "v", away = "", day = ""] = slide.lines;
  for (const [text, y] of [[home, 82], [away, 142]] as const) {
    const name = foldText(text).toUpperCase();
    centred(ctx, name, y, WHITE, fitScale(name, 440, 4), INK);
  }
  centred(ctx, versus.toUpperCase(), 116, GOLD, 3, INK);
  centred(ctx, foldText(day).toUpperCase(), 206, "#c9d8f2", 2);
}

function breaking(ctx: CanvasRenderingContext2D, slide: Slide, local: number, clock: number): void {
  const lit = Math.floor(clock * 3) % 2 === 0;
  frame(ctx, lit ? FLASH_A : FLASH_B, local);
  for (const x of [14, STUDIO_W - 34]) {
    for (let step = 0; step < 4; step += 1) fill(ctx, lit ? WHITE : GOLD, x, 24 + step * 22, 20, 12);
  }
  centred(ctx, "BREAKING", 38, WHITE, 5, INK);
  centred(ctx, "NEWS", 80, WHITE, 5, INK);
  fill(ctx, "#05090f", 30, 136, STUDIO_W - 60, 88);
  const text = foldText(slide.lines[0] ?? "").toUpperCase();
  const size = [3, 2, 1].find((scale) => wrapText(text, STUDIO_W - 90, scale).length <= 3) ?? 1;
  const lines = wrapText(text, STUDIO_W - 90, size).slice(0, 3);
  const top = 136 + Math.floor((88 - lines.length * (size * 8 + 3)) / 2);
  lines.forEach((line, row) => centred(ctx, line, top + row * (size * 8 + 3), WHITE, size));
}

/** Draw the break's cards at `t` seconds in; `clock` drives the flashing and the moving stripes. */
export function drawSlides(ctx: CanvasRenderingContext2D, slides: Slide[], t: number, clock: number): void {
  const { index, local } = slideAt(slides, t);
  const slide = slides[index];
  fill(ctx, "#05090f", 0, 0, STUDIO_W, STUDIO_H);
  if (slide === undefined) return;
  if (index > 0) {
    const before = slides[index - 1]!;
    fill(ctx, before.kind === "table" || before.kind === "results" ? BLUE : before.dark, 0, 0, STUDIO_W, FIELD_H);
  }
  if (slide.kind === "ad") ad(ctx, slide, local, clock);
  else if (slide.kind === "table" || slide.kind === "results") board(ctx, slide, local, clock);
  else if (slide.kind === "fixture") fixture(ctx, slide, local, clock);
  else breaking(ctx, slide, local, clock);
  slides.forEach((_, dot) => fill(ctx, dot === index ? GOLD : "#ffffff", STUDIO_W / 2 - slides.length * 6 + dot * 12, FIELD_H - 8, 6, 4, dot === index ? 1 : 0.35));
}
