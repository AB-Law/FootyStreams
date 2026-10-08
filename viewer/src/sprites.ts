import type { Appearance } from "./meta.ts";
import { hairColour, shirtColour, skinColour, type Kit } from "./palette.ts";

export interface Dress {
  kit: Kit;
  /** Shirt colour that replaces the kit for a goalkeeper, or null. */
  keeper: string | null;
  appearance: Appearance;
}

const SHADOW = "rgba(0, 0, 0, 0.30)";
const OUTLINE = "#12161c";
const CARRIER_MARK = "#fff36b";
const STRIDE_SECONDS = 0.18;
const EYE = "#1b1b1b";
const BOOT = "#1b1b1b";
const KEEPER_SHORTS = "#222222";

/**
 * Sprite art: 7 wide, 11 tall, one string per row. h hair, s skin, e eye, a sleeve, j shirt,
 * k shorts, l sock, b boot. Three leg poses: standing, and two strides.
 */
const BODY = ["..hhh..", ".hhhhh.", ".seses.", "..sss..", "ajjjjja", "ajjjjja", "sjjjjjs", ".kkkkk."] as const;
const LEGS = {
  stand: [".kk.kk.", ".ll.ll.", ".bb.bb."],
  stepA: [".kk.kk.", "ll...l.", "bb...b."],
  stepB: [".kk.kk.", ".l...ll", ".b...bb"],
} as const;
export const BIG_WIDTH = 7;
export const BIG_HEIGHT = BODY.length + 3;

/** The small sprite used when the whole pitch is on screen: 5 wide, 7 tall. */
export const SMALL_WIDTH = 5;
export const SMALL_HEIGHT = 7;

type Pose = keyof typeof LEGS;

const cache = new Map<string, HTMLCanvasElement>();

function colourOf(char: string, dress: Dress, column: number, row: number): string | null {
  const skin = skinColour(dress.appearance);
  switch (char) {
    case "h":
      return dress.appearance.hair_style === "bald" ? skin : hairColour(dress.appearance);
    case "s":
      return skin;
    case "e":
      return EYE;
    case "a":
      return dress.keeper ?? dress.kit.primary;
    case "j":
      return dress.keeper ?? shirtColour(dress.kit, Math.max(column - 1, 0), Math.max(row - 4, 0));
    case "k":
      return dress.keeper === null ? dress.kit.secondary : KEEPER_SHORTS;
    case "l":
      return dress.kit.primary;
    case "b":
      return BOOT;
    default:
      return null;
  }
}

/** The head rows, changed for hair and facial hair. */
function head(appearance: Appearance): string[] {
  const rows: string[] = ["..hhh..", ".hhhhh.", ".seses.", "..sss.."];
  switch (appearance.hair_style) {
    case "long":
    case "braids":
      rows[2] = "hsesesh";
      rows[3] = ".hsssh.";
      break;
    case "curly":
      rows[0] = ".hhhhh.";
      rows[1] = "hhhhhhh";
      break;
    case "buzz":
    case "fade":
      rows[1] = ".sssss.";
      break;
    default:
      break;
  }
  if (appearance.facial_hair === "beard" || appearance.facial_hair === "goatee") rows[3] = "..hhh..";
  return rows;
}

function render(dress: Dress, pose: Pose): HTMLCanvasElement {
  const rows = [...head(dress.appearance), ...BODY.slice(4), ...LEGS[pose]];
  const canvas = document.createElement("canvas");
  canvas.width = BIG_WIDTH + 2;
  canvas.height = rows.length + 2;
  const ctx = canvas.getContext("2d");
  if (ctx === null) return canvas;
  const filled = (column: number, row: number): boolean => (rows[row]?.[column] ?? ".") !== ".";
  rows.forEach((_line, row) => {
    for (let column = 0; column < BIG_WIDTH; column++) {
      if (!filled(column, row)) continue;
      for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1]] as const) {
        if (filled(column + dx, row + dy)) continue;
        ctx.fillStyle = OUTLINE;
        ctx.fillRect(column + 1 + dx, row + 1 + dy, 1, 1);
      }
    }
  });
  rows.forEach((line, row) => {
    for (let column = 0; column < BIG_WIDTH; column++) {
      const colour = colourOf(line[column] ?? ".", dress, column, row);
      if (colour === null) continue;
      ctx.fillStyle = colour;
      ctx.fillRect(column + 1, row + 1, 1, 1);
    }
  });
  return canvas;
}

function sprite(dress: Dress, pose: Pose): HTMLCanvasElement {
  const { kit, appearance, keeper } = dress;
  const key = [kit.pattern, kit.primary, kit.secondary, keeper, appearance.skin_tone, appearance.hair_colour, appearance.hair_style, appearance.facial_hair, pose].join("|");
  let found = cache.get(key);
  if (found === undefined) {
    found = render(dress, pose);
    cache.set(key, found);
  }
  return found;
}

function pixel(ctx: CanvasRenderingContext2D, colour: string, x: number, y: number, width = 1): void {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, width, 1);
}

/** The five-by-seven player of the whole-pitch view. */
function drawSmall(ctx: CanvasRenderingContext2D, x: number, y: number, dress: Dress, running: boolean, phase: number): void {
  const left = x - Math.floor(SMALL_WIDTH / 2);
  const top = y - SMALL_HEIGHT + 1;
  const skin = skinColour(dress.appearance);
  pixel(ctx, SHADOW, left, y + 1, SMALL_WIDTH);
  pixel(ctx, dress.appearance.hair_style === "bald" ? skin : hairColour(dress.appearance), left + 1, top, 3);
  pixel(ctx, skin, left + 1, top + 1, 3);
  for (let row = 0; row < 3; row++) {
    for (const column of row === 0 ? [0, 1, 2, 3, 4] : [1, 2, 3]) {
      pixel(ctx, dress.keeper ?? shirtColour(dress.kit, column, row), left + column, top + 2 + row);
    }
  }
  pixel(ctx, dress.keeper === null ? dress.kit.secondary : KEEPER_SHORTS, left + 1, top + 5, 3);
  const step = running && Math.floor(phase / STRIDE_SECONDS) % 2 === 0;
  pixel(ctx, dress.kit.primary, left + 1, top + 6);
  pixel(ctx, dress.kit.primary, left + (step ? 2 : 3), top + 6);
}

export interface DrawOptions {
  running: boolean;
  /** The clock in seconds, for the stride. */
  phase: number;
  /** True for the large sprite of the zoomed camera. */
  big: boolean;
}

/** Draw one player with the feet at (x, y). */
export function drawPlayer(ctx: CanvasRenderingContext2D, x: number, y: number, dress: Dress, options: DrawOptions): void {
  if (!options.big) {
    drawSmall(ctx, x, y, dress, options.running, options.phase);
    return;
  }
  pixel(ctx, SHADOW, x - 3, y, 7);
  pixel(ctx, SHADOW, x - 2, y + 1, 5);
  const stride = Math.floor(options.phase / STRIDE_SECONDS) % 2 === 0 ? "stepA" : "stepB";
  ctx.drawImage(sprite(dress, options.running ? stride : "stand"), x - 4, y - BIG_HEIGHT);
}

/** A small arrow above the head of the player on the ball. */
export function drawCarrierMark(ctx: CanvasRenderingContext2D, x: number, y: number, big: boolean): void {
  const top = y - (big ? BIG_HEIGHT + 4 : SMALL_HEIGHT + 3);
  pixel(ctx, CARRIER_MARK, x - 1, top, 3);
  pixel(ctx, CARRIER_MARK, x, top + 1);
}

/** The ball at ground point (x, y), lifted `height` pixels, with its shadow left on the grass. */
export function drawBall(ctx: CanvasRenderingContext2D, x: number, y: number, height: number): void {
  ctx.fillStyle = SHADOW;
  ctx.fillRect(x - 1, y + 1, 3, 1);
  const lift = Math.round(height);
  ctx.fillStyle = OUTLINE;
  ctx.fillRect(x - 2, y - 2 - lift, 4, 4);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(x - 1, y - 1 - lift, 2, 2);
  ctx.fillStyle = "#b9c2cc";
  ctx.fillRect(x, y - lift, 1, 1);
}

/** Fading dots behind a fast ball, so a shot reads as speed. */
export function drawTrail(ctx: CanvasRenderingContext2D, points: { x: number; y: number; height: number }[]): void {
  points.forEach((point, index) => {
    ctx.fillStyle = `rgba(255, 255, 255, ${0.5 - index * 0.15})`;
    ctx.fillRect(point.x - 1, point.y - 1 - Math.round(point.height), 2, 2);
  });
}
