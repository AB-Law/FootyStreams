import { drawCentred, drawText, textWidth } from "./font.ts";
import type { Sample } from "./interpolate.ts";
import { playerName, type ReplayMeta, type TeamSide } from "./meta.ts";
import type { ActiveOverlay } from "./overlays.ts";
import type { Kit } from "./palette.ts";
import { HEIGHT, PITCH, WIDTH } from "./pitch.ts";
import type { Scene } from "./scene.ts";
import type { CardColour, Mark } from "./store.ts";

const PANEL = "#0d1620";
const PANEL_EDGE = "#3b5068";
const TEXT = "#f2f6fa";
const MUTED = "#8fa3b8";
const GOLD = "#ffd23f";
const CARD_COLOURS: Record<CardColour, string> = { yellow: "#ffd23f", red: "#e63946", second_yellow: "#e63946" };
const CARD_LABELS: Record<CardColour, string> = { yellow: "YELLOW CARD", red: "RED CARD", second_yellow: "SECOND YELLOW" };
const FLASH_PERIOD = 0.12;
const NOTE_HEIGHT = 17;
const NOTE_BASELINE = HEIGHT - 8;

function panel(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, edge = PANEL_EDGE): void {
  ctx.fillStyle = edge;
  ctx.fillRect(x - 1, y - 1, width + 2, height + 2);
  ctx.fillStyle = PANEL;
  ctx.fillRect(x, y, width, height);
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function phaseLabel(period: number): string {
  return period === 1 ? "1ST" : "2ND";
}

/** Scoreboard along the top: home swatch, code and score, away, then the clock. */
export function drawScoreboard(
  ctx: CanvasRenderingContext2D,
  sample: Sample | null,
  meta: ReplayMeta,
  kits: Record<TeamSide, Kit>,
  finished: boolean,
): void {
  const width = 200;
  const left = Math.round((WIDTH - width) / 2);
  panel(ctx, left, 3, width, 17);
  const score = sample === null ? "0 - 0" : `${sample.scoreHome} - ${sample.scoreAway}`;
  ctx.fillStyle = kits.home.primary;
  ctx.fillRect(left + 4, 7, 4, 9);
  ctx.fillStyle = kits.home.secondary;
  ctx.fillRect(left + 8, 7, 2, 9);
  drawText(ctx, meta.home.short_code, left + 13, 9, TEXT, 2);
  drawCentred(ctx, score, WIDTH / 2, 9, GOLD, 2);
  const awayCode = meta.away.short_code;
  drawText(ctx, awayCode, left + width - 13 - textWidth(awayCode, 2) - 0, 9, TEXT, 2);
  ctx.fillStyle = kits.away.primary;
  ctx.fillRect(left + width - 10, 7, 2, 9);
  ctx.fillStyle = kits.away.secondary;
  ctx.fillRect(left + width - 8, 7, 4, 9);
  if (sample === null) return;
  const clock = finished ? "FT" : `${pad(sample.clock.minute)}:${pad(sample.clock.second)}`;
  panel(ctx, left + width + 4, 3, 36, 17);
  drawText(ctx, clock, left + width + 8, 5, TEXT, 1);
  drawText(ctx, finished ? "" : phaseLabel(sample.clock.period), left + width + 8, 12, MUTED, 1);
}

function flashing(progress: number, window: number): boolean {
  return Math.floor((progress * window) / FLASH_PERIOD) % 2 === 0;
}

function drawGoal(
  ctx: CanvasRenderingContext2D,
  mark: Extract<Mark, { kind: "goal" }>,
  progress: number,
  meta: ReplayMeta,
): void {
  const height = 52;
  const top = Math.round(PITCH.y + PITCH.height / 2 - height / 2);
  const edge = flashing(progress, 4.5) ? GOLD : "#ffffff";
  panel(ctx, 40, top, WIDTH - 80, height, edge);
  drawCentred(ctx, "GOAL!", WIDTH / 2, top + 5, GOLD, 4);
  const who = playerName(meta, mark.scorerId) + (mark.ownGoal ? " (OWN GOAL)" : "");
  drawCentred(ctx, who, WIDTH / 2, top + 29, TEXT, 2);
  const line = `${meta.home.short_code} ${mark.scoreHome} - ${mark.scoreAway} ${meta.away.short_code}   ${mark.minute}'`;
  drawCentred(ctx, line, WIDTH / 2, top + 43, MUTED, 1);
}

/** A card shown over the player, plus a coloured frame around the pitch while it flashes. */
function drawCard(
  ctx: CanvasRenderingContext2D,
  mark: Extract<Mark, { kind: "card" }>,
  progress: number,
  at: { x: number; y: number } | null,
): void {
  const colour = CARD_COLOURS[mark.colour];
  if (flashing(progress, 2.5)) {
    ctx.fillStyle = colour;
    for (const [x, y, w, h] of [
      [PITCH.x, PITCH.y, PITCH.width, 2],
      [PITCH.x, PITCH.y + PITCH.height - 2, PITCH.width, 2],
      [PITCH.x, PITCH.y, 2, PITCH.height],
      [PITCH.x + PITCH.width - 2, PITCH.y, 2, PITCH.height],
    ] as const) ctx.fillRect(x, y, w, h);
  }
  if (at === null) return;
  ctx.fillStyle = "#101418";
  ctx.fillRect(at.x - 3, at.y - 21, 6, 9);
  ctx.fillStyle = colour;
  ctx.fillRect(at.x - 2, at.y - 20, 4, 7);
}

function drawNote(ctx: CanvasRenderingContext2D, slot: number, title: string, detail: string, accent: string): void {
  const width = Math.max(textWidth(title), textWidth(detail)) + 12;
  const top = NOTE_BASELINE - NOTE_HEIGHT - slot * (NOTE_HEIGHT + 3);
  panel(ctx, 14, top, width, NOTE_HEIGHT, accent);
  drawText(ctx, title, 20, top + 3, accent, 1);
  drawText(ctx, detail, 20, top + 10, TEXT, 1);
}

function noteText(mark: Mark, meta: ReplayMeta): { title: string; detail: string; accent: string } | null {
  if (mark.kind === "card") {
    const team = mark.team === "none" ? "" : meta[mark.team].short_code;
    return { title: `${CARD_LABELS[mark.colour]} ${team}`, detail: playerName(meta, mark.playerId), accent: CARD_COLOURS[mark.colour] };
  }
  if (mark.kind === "substitution") {
    const team = mark.team === "none" ? "" : meta[mark.team].short_code;
    return { title: `SUBSTITUTION ${team}`, detail: `ON ${playerName(meta, mark.onId)}  OFF ${playerName(meta, mark.offId)}`, accent: "#5ec2ff" };
  }
  return null;
}

function drawBreak(ctx: CanvasRenderingContext2D, mark: Extract<Mark, { kind: "halftime" | "fulltime" }>, meta: ReplayMeta): void {
  const title = mark.kind === "halftime" ? "HALF TIME" : "FULL TIME";
  const top = Math.round(PITCH.y + PITCH.height / 2 - 14);
  panel(ctx, 80, top, WIDTH - 160, 28);
  drawCentred(ctx, title, WIDTH / 2, top + 4, TEXT, 2);
  drawCentred(ctx, `${meta.home.short_code} ${mark.scoreHome} - ${mark.scoreAway} ${meta.away.short_code}`, WIDTH / 2, top + 19, MUTED, 1);
}

/** Draw every active overlay: goal and break banners centred, cards on the pitch, notes stacked. */
export function drawOverlays(
  ctx: CanvasRenderingContext2D,
  active: readonly ActiveOverlay[],
  meta: ReplayMeta,
  scene: Scene,
  sample: Sample | null,
): void {
  let slot = 0;
  for (const { mark, progress } of active) {
    if (mark.kind === "goal") drawGoal(ctx, mark, progress, meta);
    else if (mark.kind === "halftime" || mark.kind === "fulltime") drawBreak(ctx, mark, meta);
    else {
      if (mark.kind === "card") {
        const at = sample === null ? null : scene.screenPosition(sample, mark.playerId);
        drawCard(ctx, mark, progress, at);
      }
      const note = noteText(mark, meta);
      if (note !== null) drawNote(ctx, slot++, note.title, note.detail, note.accent);
    }
  }
}
