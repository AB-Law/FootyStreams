import type { Appearance } from "./meta.ts";
import { hairColour, shirtColour, skinColour } from "./palette.ts";
import { BIG_HEIGHT, BIG_WIDTH, BOOT, KEEPER_SHORTS, OUTLINE, SHADOW, SMALL_HEIGHT, STRIDE_SECONDS, colourOf, pixel, type Dress } from "./sprites.ts";

// Side-on players for the broadcast view. The art faces right and is flipped to face left. Row
// letters: h hair, s skin, e eye, a sleeve, j shirt, k shorts, l sock, b boot, . empty.

/** A pose of a profile player: the first three are the walk and run, the rest are skills. */
export type ProfilePose = "stand" | "stepA" | "stepB" | "lean" | "feint" | "kick" | "flick";

const HEAD = ["..hhh..", ".hhhhh.", ".hhsse.", "..hsss."] as const;
const LEGS: Record<ProfilePose, readonly string[]> = {
  stand: ["..k.k..", "..l.l..", "..b.bb."],
  stepA: [".l...l.", ".l...l.", "bb...bb"],
  stepB: ["..l.l..", "..l.l..", "..b.bb."],
  lean: [".l...l.", ".l...l.", "bb...bb"],
  feint: ["..l..l.", "..l...l", "..b...b"],
  kick: [".l....l", ".l...l.", "bb..bb."],
  flick: ["..l.l..", "..l..l.", "..b.bb."],
};
/** Torso rows (arms swing with the stride) ending in the shorts. */
const TORSO: Record<ProfilePose, readonly string[]> = {
  stand: ["..jaj..", "..jaj..", "..jjj..", "..kkk.."],
  stepA: [".ajjj..", ".ajjja.", "..jjj..", "..kkk.."],
  stepB: ["..jjja.", "..jjj..", ".ajjj..", "..kkk.."],
  lean: ["..jjja.", "..jjjaa", "..jjj..", "..kkk.."],
  feint: ["..jaj..", ".ajjja.", "..jjj..", "..kkk.."],
  kick: [".ajjj..", "..jjj..", ".ajjja.", "..kkk.."],
  flick: [".ajjja.", "..jjj..", "..jjj..", "..kkk.."],
};

const cache = new Map<string, HTMLCanvasElement>();

function headRows(appearance: Appearance): string[] {
  const rows: string[] = [...HEAD];
  if (appearance.hair_style === "long" || appearance.hair_style === "braids") rows[3] = ".hhsss.";
  if (appearance.hair_style === "buzz" || appearance.hair_style === "fade") rows[1] = ".hhhss.";
  if (appearance.facial_hair === "beard" || appearance.facial_hair === "goatee") rows[3] = "..hhhh.";
  return rows;
}

function sprite(dress: Dress, pose: ProfilePose): HTMLCanvasElement {
  const { kit, appearance, keeper } = dress;
  const key = [kit.pattern, kit.primary, kit.secondary, keeper, appearance.skin_tone, appearance.hair_colour, appearance.hair_style, appearance.facial_hair, pose].join("|");
  const found = cache.get(key);
  if (found !== undefined) return found;
  const rows = [...headRows(appearance), ...TORSO[pose], ...LEGS[pose]];
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
  cache.set(key, canvas);
  return canvas;
}

export interface ProfileOptions {
  /** 1 faces right, -1 faces left. */
  facing: 1 | -1;
  running: boolean;
  /** The clock in seconds, for the stride. */
  phase: number;
  big: boolean;
  /** A skill or a kick overrides the walk and run poses. */
  pose?: ProfilePose;
  lying?: 1 | -1;
  arms?: boolean;
}

/** The legs through a stride: reaching, passing, reaching the other way, passing. */
function strideOf(phase: number): ProfilePose {
  const step = Math.floor(phase / STRIDE_SECONDS) % 4;
  return step === 0 ? "stepA" : "stepB";
}

/** The five-by-seven side-on player of the wide view, facing right or left. */
function drawSmall(ctx: CanvasRenderingContext2D, x: number, y: number, dress: Dress, options: ProfileOptions): void {
  const skin = skinColour(dress.appearance);
  const sign = options.facing;
  const put = (colour: string, dx: number, dy: number): void => {
    ctx.fillStyle = colour;
    ctx.fillRect(sign > 0 ? x + dx : x - dx - 1, y - SMALL_HEIGHT + 1 + dy, 1, 1);
  };
  ctx.fillStyle = SHADOW;
  ctx.fillRect(x - 3, y + 1, 7, 1);
  const hair = dress.appearance.hair_style === "bald" ? skin : hairColour(dress.appearance);
  put(hair, -1, 0);
  put(hair, 0, 0);
  put(skin, 1, 0);
  put(skin, 0, 1);
  put(hair, -1, 1);
  for (const dx of [-1, 0, 1]) {
    put(dress.keeper ?? shirtColour(dress.kit, dx + 1, 0), dx, 2);
    put(dress.keeper ?? shirtColour(dress.kit, dx + 1, 1), dx, 3);
  }
  const shorts = dress.keeper === null ? dress.kit.secondary : KEEPER_SHORTS;
  put(shorts, -1, 4);
  put(shorts, 0, 4);
  const pose = options.pose ?? (options.running ? strideOf(options.phase) : "stand");
  const spread = pose === "stand" || pose === "stepB" ? 0 : 1;
  put(dress.kit.primary, -1 - spread, 5);
  put(dress.kit.primary, spread, 5);
  put(BOOT, -1 - spread, 6);
  put(BOOT, spread, 6);
}

/** Draw one player side-on with the feet at (x, y), facing the way he is going. */
export function drawProfilePlayer(ctx: CanvasRenderingContext2D, x: number, y: number, dress: Dress, options: ProfileOptions): void {
  if (!options.big) {
    drawSmall(ctx, x, y, dress, options);
    return;
  }
  pixel(ctx, SHADOW, x - 3, y, 7);
  pixel(ctx, SHADOW, x - 2, y + 1, 5);
  if (options.lying !== undefined) {
    ctx.save();
    ctx.translate(x, y - 2);
    ctx.rotate((options.lying > 0 ? -Math.PI : Math.PI) / 2);
    ctx.drawImage(sprite(dress, "stand"), -4, -BIG_HEIGHT / 2);
    ctx.restore();
    return;
  }
  const pose = options.pose ?? (options.running ? strideOf(options.phase) : "stand");
  ctx.save();
  ctx.translate(x, 0);
  ctx.scale(options.facing, 1);
  ctx.drawImage(sprite(dress, pose), -4, y - BIG_HEIGHT);
  ctx.restore();
  if (options.arms === true) {
    const skin = skinColour(dress.appearance);
    for (const side of [-1, 1]) {
      ctx.fillStyle = OUTLINE;
      ctx.fillRect(x + side - 1, y - BIG_HEIGHT - 4, 3, 7);
      ctx.fillStyle = skin;
      ctx.fillRect(x + side, y - BIG_HEIGHT - 3, 1, 5);
    }
  }
}
