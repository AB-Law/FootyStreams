import type { Appearance } from "./meta.ts";
import { hairColour, shirtColour, skinColour, type Kit } from "./palette.ts";

/** Sprite size in pixels; the feet are on the bottom row, centred on the player's position. */
export const SPRITE_WIDTH = 5;
export const SPRITE_HEIGHT = 7;
const STRIDE_SECONDS = 0.18;
const SHADOW = "rgba(0, 0, 0, 0.28)";
const CARRIER_MARK = "#fff36b";

export interface Dress {
  kit: Kit;
  /** Shirt colour that replaces the kit for a goalkeeper, or null. */
  keeper: string | null;
  appearance: Appearance;
}

function pixel(ctx: CanvasRenderingContext2D, colour: string, x: number, y: number, width = 1): void {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, width, 1);
}

function drawHead(ctx: CanvasRenderingContext2D, left: number, top: number, appearance: Appearance): void {
  const skin = skinColour(appearance);
  const hair = appearance.hair_style === "bald" ? skin : hairColour(appearance);
  pixel(ctx, hair, left + 1, top, 3);
  pixel(ctx, skin, left + 1, top + 1, 3);
  if (appearance.hair_style === "long" || appearance.hair_style === "braids") {
    pixel(ctx, hair, left, top + 1);
    pixel(ctx, hair, left + 4, top + 1);
  }
  if (appearance.hair_style === "curly") pixel(ctx, hair, left, top, 5);
  if (appearance.facial_hair === "beard" || appearance.facial_hair === "goatee") {
    pixel(ctx, hair, left + 2, top + 1);
  }
}

function drawBody(ctx: CanvasRenderingContext2D, left: number, top: number, dress: Dress): void {
  for (let row = 0; row < 3; row++) {
    const columns = row === 0 ? [0, 1, 2, 3, 4] : [1, 2, 3];
    for (const column of columns) {
      const colour = dress.keeper ?? shirtColour(dress.kit, column, row);
      pixel(ctx, colour, left + column, top + 2 + row);
    }
  }
  pixel(ctx, dress.keeper === null ? dress.kit.secondary : "#222222", left + 1, top + 5, 3);
}

/** Draw one player with the feet at (x, y). `phase` is the clock in seconds, for the stride. */
export function drawPlayer(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  dress: Dress,
  running: boolean,
  phase: number,
): void {
  const left = x - Math.floor(SPRITE_WIDTH / 2);
  const top = y - SPRITE_HEIGHT + 1;
  pixel(ctx, SHADOW, left, y + 1, SPRITE_WIDTH);
  drawHead(ctx, left, top, dress.appearance);
  drawBody(ctx, left, top, dress);
  const sock = dress.kit.primary;
  const step = running && Math.floor(phase / STRIDE_SECONDS) % 2 === 0;
  pixel(ctx, sock, left + 1, top + 6);
  pixel(ctx, sock, left + (step ? 2 : 3), top + 6);
}

/** A small arrow above the head of the player on the ball. */
export function drawCarrierMark(ctx: CanvasRenderingContext2D, x: number, y: number): void {
  const top = y - SPRITE_HEIGHT - 3;
  pixel(ctx, CARRIER_MARK, x - 1, top, 3);
  pixel(ctx, CARRIER_MARK, x, top + 1);
}

export function drawBall(ctx: CanvasRenderingContext2D, x: number, y: number): void {
  ctx.fillStyle = SHADOW;
  ctx.fillRect(x, y + 1, 2, 2);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(x - 1, y - 1, 2, 2);
}
