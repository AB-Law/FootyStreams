import type { MatchResult, Screen } from "./commentary.ts";
import { clipText, drawShadowed, drawText, foldText, textWidth, wrapText } from "./pixelfont.ts";
import { fill, LEFT_SCREEN, RIGHT_SCREEN, STUDIO_W, type Rect } from "./studio-set.ts";

// The screens on the wall, the ON AIR sign and the channel bug: broadcast furniture that changes
// with the line being read or with the clock.

const BLUE = "#0d3b8c";
const BLUE_DARK = "#0a2c6b";
const GOLD = "#f2c200";
const RED = "#c8102e";
const WHITE = "#f4f7fb";
const INK = "#101418";
const PAD = 6;
const CONTENT_TOP = 16;

function screenBase(ctx: CanvasRenderingContext2D, screen: Rect, strip: string, stripText: string, stripInk: string): void {
  fill(ctx, BLUE, screen.x, screen.y, screen.w, screen.h);
  for (let y = screen.y + 14; y < screen.y + screen.h; y += 4) fill(ctx, BLUE_DARK, screen.x, y, screen.w, 1);
  fill(ctx, strip, screen.x, screen.y, screen.w, 12);
  drawText(ctx, clipText(stripText, screen.w - 2 * PAD), screen.x + PAD, screen.y + 3, stripInk);
}

/** What the left screen says: a topic, and for a notice (stand by, up next) a line of detail under it. */
export interface Topic {
  label: string;
  detail?: string;
}

/** The left screen: what the desk is covering now, or what is coming. */
export function drawTopicScreen(ctx: CanvasRenderingContext2D, topic: Topic): void {
  const screen = LEFT_SCREEN;
  screenBase(ctx, screen, GOLD, "VPL NEWS", INK);
  fill(ctx, RED, screen.x + screen.w - 28, screen.y + 3, 22, 6);
  drawText(ctx, "DESK", screen.x + screen.w - 26, screen.y + 4, WHITE);
  const room = screen.w - 20;
  const lines = wrapText(foldText(topic.label).toUpperCase(), room, 2).slice(0, 2);
  const detail = topic.detail ? wrapText(foldText(topic.detail), room).slice(0, 2) : [];
  const height = lines.length * 16 + detail.length * 10;
  const top = screen.y + CONTENT_TOP + Math.max(Math.floor((screen.h - CONTENT_TOP - 8 - height) / 2), 0);
  lines.forEach((line, row) => {
    const width = textWidth(line, 2);
    drawShadowed(ctx, line, screen.x + Math.floor((screen.w - width) / 2), top + row * 16, WHITE, INK, 2);
  });
  detail.forEach((line, row) => {
    drawText(ctx, line, screen.x + Math.floor((screen.w - textWidth(line)) / 2), top + lines.length * 16 + 1 + row * 10, "#c9d8f2");
  });
  fill(ctx, RED, screen.x, screen.y + screen.h - 6, screen.w, 3);
  fill(ctx, GOLD, screen.x, screen.y + screen.h - 3, screen.w, 3);
}

function scoreRow(ctx: CanvasRenderingContext2D, screen: Rect, row: number, name: string, goals: string): void {
  const y = screen.y + 17 + row * 19;
  const chip = screen.x + screen.w - 28;
  fill(ctx, "#08224f", screen.x + PAD, y, screen.w - 2 * PAD, 16);
  fill(ctx, GOLD, screen.x + PAD, y, 2, 16);
  drawShadowed(ctx, clipText(name, chip - screen.x - 20).toUpperCase(), screen.x + 13, y + 5, WHITE, INK);
  fill(ctx, WHITE, chip, y + 1, 21, 14);
  drawText(ctx, goals, chip + Math.floor((21 - textWidth(goals, 2)) / 2), y + 1, INK, 2);
}

function tableRows(ctx: CanvasRenderingContext2D, screen: Rect, screenRows: Screen["rows"]): void {
  screenRows.slice(0, 5).forEach((row, index) => {
    const y = screen.y + CONTENT_TOP + index * 9;
    if (index % 2 === 0) fill(ctx, "#08224f", screen.x + PAD, y - 1, screen.w - 2 * PAD, 9);
    const value = row.value ?? "";
    const room = screen.w - 2 * PAD - textWidth(value) - 14;
    drawText(ctx, String(index + 1), screen.x + PAD + 2, y, GOLD);
    drawText(ctx, clipText(row.label, room).toUpperCase(), screen.x + PAD + 10, y, WHITE);
    drawText(ctx, value.toUpperCase(), screen.x + screen.w - PAD - 2 - textWidth(value), y, "#c9d8f2");
  });
}

function cardRows(ctx: CanvasRenderingContext2D, screen: Rect, screenRows: Screen["rows"]): void {
  screenRows.slice(0, 4).forEach((row, index) => {
    const y = screen.y + CONTENT_TOP + 4 + index * 11;
    const label = `${foldText(row.label).toUpperCase()}`;
    drawText(ctx, label, screen.x + PAD + 2, y, GOLD);
    const value = clipText(row.value ?? "", screen.w - 2 * PAD - textWidth(label) - 10).toUpperCase();
    drawShadowed(ctx, value, screen.x + screen.w - PAD - 2 - textWidth(value), y, WHITE, INK);
  });
}

/** The right screen: a score, a table or a fact card; with none, the score from the intro, or the channel name. */
export function drawRightScreen(ctx: CanvasRenderingContext2D, screen: Screen | null, fallback: MatchResult | null): void {
  const area = RIGHT_SCREEN;
  const shown: Screen | null =
    screen ??
    (fallback
      ? {
          kind: "score",
          title: "RESULT",
          rows: [
            { label: fallback.home, value: String(fallback.homeGoals) },
            { label: fallback.away, value: String(fallback.awayGoals) },
          ],
        }
      : null);
  if (shown === null) {
    screenBase(ctx, area, RED, "VPL NEWS", WHITE);
    const width = textWidth("VPL NEWS", 2);
    drawShadowed(ctx, "VPL NEWS", area.x + Math.floor((area.w - width) / 2), area.y + 28, GOLD, INK, 2);
    return;
  }
  screenBase(ctx, area, RED, foldText(shown.title).toUpperCase(), WHITE);
  if (shown.kind === "score") shown.rows.slice(0, 2).forEach((row, index) => scoreRow(ctx, area, index, row.label, row.value ?? ""));
  else if (shown.kind === "table") tableRows(ctx, area, shown.rows);
  else cardRows(ctx, area, shown.rows);
}

/** The ON AIR sign hanging from the ceiling; its glow breathes slowly. */
export function drawOnAir(ctx: CanvasRenderingContext2D, t: number): void {
  const x = Math.floor((STUDIO_W - 50) / 2);
  const pulse = Math.floor(2 + 2 * Math.sin(t * 2.4));
  fill(ctx, "#ff2a2a", x - 4, 0, 58, 14, 0.04 * pulse);
  fill(ctx, "#05090f", x - 1, 0, 52, 13);
  fill(ctx, "#3a0c10", x, 0, 50, 12);
  drawText(ctx, "ON AIR", x + 10, 3, pulse > 2 ? "#ff5a4a" : "#ff3b3b");
}

/** The channel bug on the left and the LIVE (or REPLAY) tag on the right, both on the ceiling strip. */
export function drawBug(ctx: CanvasRenderingContext2D, t: number, replay = false): void {
  fill(ctx, GOLD, 8, 2, 38, 11);
  drawText(ctx, "VPL 1", 14, 4, INK);
  const width = replay ? 48 : 36;
  const x = STUDIO_W - 8 - width;
  fill(ctx, replay ? "#8a5a00" : RED, x, 2, width, 11);
  if (!replay && Math.floor(t * 1.5) % 2 === 0) fill(ctx, WHITE, x + 5, 5, 4, 4);
  drawText(ctx, replay ? "REPLAY" : "LIVE", x + (replay ? 6 : 12), 4, WHITE);
}
