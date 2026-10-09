import type { Appearance } from "./meta.ts";
import { hairColour, shirtColour, skinColour, type Kit } from "./palette.ts";

// Players for the broadcast view are drawn as small articulated figures: a skeleton of thighs,
// shins, arms, torso and head posed by joint angles, painted pixel by pixel (no anti-aliasing) onto
// a grid, outlined, and cached per look and pose. The figure faces right and is flipped to face
// left. Angles are in radians from straight down, positive swinging forward.

export const FIGURE_W = 48;
export const FIGURE_H = 54;
/** Where the feet stand on the grid. */
export const FEET_X = 24;
export const FEET_Y = 47;
/** A full-size figure is about this many grid pixels from boots to crown (1.8 m). */
export const FIGURE_HEIGHT_PX = 31;

const OUTLINE = "#10141a";
const BOOT = "#1c1c20";
const SOLE = "#e9e9ee";
const GLOVE = "#f4f4f6";
const KEEPER_SHORTS = "#202226";
const EYE = "#14161b";
const WHITE = "#ffffff";
const THIGH = 6.2;
const SHIN = 6;
const UPPER_ARM = 4.2;
const FOREARM = 4;
const TORSO = 7;
const HEAD_RADIUS = 4.7;
const LEG_LENGTH = THIGH + SHIN;
/** Far-side limbs and the back of the figure are a little darker, for depth. */
const FAR_SHADE = 0.74;

export interface FigureDress {
  kit: Kit;
  /** Shirt colour that replaces the kit for a goalkeeper, or null. */
  keeper: string | null;
  appearance: Appearance;
}

export type FigurePose = "stand" | "run" | "lean" | "feint" | "kick" | "flick" | "throw";

interface Leg {
  a: number;
  k: number;
}

interface Arm {
  c: number;
  e: number;
}

interface Joints {
  bob: number;
  lean: number;
  near: Leg;
  far: Leg;
  nearArm: Arm;
  farArm: Arm;
}

function swing(phase: number, amp: number): Joints {
  const t = 2 * Math.PI * phase;
  const reach = 0.8 * amp;
  const bend = (angle: number): number => 0.12 + 0.95 * amp * Math.max(0, Math.cos(angle));
  const elbow = 0.9 + 0.4 * amp;
  return {
    bob: -1.3 * amp * Math.abs(Math.sin(t)),
    lean: 0.12 * amp,
    near: { a: reach * Math.sin(t), k: bend(t) },
    far: { a: reach * Math.sin(t + Math.PI), k: bend(t + Math.PI) },
    nearArm: { c: -0.75 * amp * Math.sin(t), e: elbow },
    farArm: { c: 0.75 * amp * Math.sin(t), e: elbow },
  };
}

function joints(pose: FigurePose, phase: number, amp: number): Joints {
  const rest: Joints = {
    bob: 0,
    lean: 0.03,
    near: { a: 0.16, k: 0.04 },
    far: { a: -0.14, k: 0 },
    nearArm: { c: -0.3, e: 0.25 },
    farArm: { c: 0.28, e: 0.25 },
  };
  switch (pose) {
    case "run":
      return swing(phase, amp);
    case "lean":
      return { ...swing(phase, amp), lean: 0.34 };
    case "feint":
      return { ...rest, bob: -0.5, lean: 0.16, near: { a: 0.95, k: 0.35 }, far: { a: -0.12, k: 0.1 }, nearArm: { c: 0.7, e: 0.5 }, farArm: { c: -0.9, e: 0.4 } };
    case "kick":
      return { ...rest, lean: -0.1, near: { a: 1.2, k: 0.1 }, far: { a: -0.2, k: 0.25 }, nearArm: { c: -0.8, e: 0.4 }, farArm: { c: 0.9, e: 0.5 } };
    case "flick":
      return { ...rest, bob: -1, lean: 0.2, near: { a: -0.95, k: 1.7 }, far: { a: 0.1, k: 0.2 }, nearArm: { c: 0.5, e: 0.6 }, farArm: { c: -0.6, e: 0.6 } };
    case "throw":
      return { ...rest, nearArm: { c: 3.0, e: 0.15 }, farArm: { c: 2.9, e: 0.15 } };
    case "stand":
      return rest;
  }
}

function hex(colour: string): [number, number, number] {
  const value = Number.parseInt(colour.replace("#", ""), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

/** A colour scaled toward black (factor under 1) or white (over 1). */
export function shade(colour: string, factor: number): string {
  const parts = hex(colour).map((channel) => {
    const moved = factor < 1 ? channel * factor : channel + (255 - channel) * (factor - 1);
    return Math.min(255, Math.max(0, Math.round(moved)));
  });
  return `#${parts.map((part) => part.toString(16).padStart(2, "0")).join("")}`;
}

function distance(a: string, b: string): number {
  const [ar, ag, ab] = hex(a);
  const [br, bg, bb] = hex(b);
  return Math.abs(ar - br) + Math.abs(ag - bg) + Math.abs(ab - bb);
}

/** The painted grid: every cell is a colour or empty. */
class Raster {
  readonly cells: (string | null)[] = new Array<string | null>(FIGURE_W * FIGURE_H).fill(null);

  set(x: number, y: number, colour: string): void {
    const column = Math.round(x);
    const row = Math.round(y);
    if (column >= 0 && column < FIGURE_W && row >= 0 && row < FIGURE_H) this.cells[row * FIGURE_W + column] = colour;
  }

  get(x: number, y: number): string | null {
    const column = Math.round(x);
    const row = Math.round(y);
    return column < 0 || column >= FIGURE_W || row < 0 || row >= FIGURE_H ? null : (this.cells[row * FIGURE_W + column] ?? null);
  }

  /** A line of squares `width` pixels across, so limbs have thickness. */
  line(x0: number, y0: number, x1: number, y1: number, width: number, colour: string): void {
    this.taper(x0, y0, width, x1, y1, width, colour);
  }

  /** A line whose thickness runs from `w0` at the start to `w1` at the end. */
  taper(x0: number, y0: number, w0: number, x1: number, y1: number, w1: number, colour: string): void {
    const steps = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 2) + 1;
    for (let step = 0; step <= steps; step++) {
      const along = step / steps;
      const x = x0 + (x1 - x0) * along;
      const y = y0 + (y1 - y0) * along;
      const width = Math.max(1, Math.round(w0 + (w1 - w0) * along));
      for (let a = 0; a < width; a++) for (let b = 0; b < width; b++) this.set(x - (width - 1) / 2 + a, y - (width - 1) / 2 + b, colour);
    }
  }

  /** A body part with straight sides: whole rows from the top to the bottom, wider or narrower down it. */
  trapezoid(xTop: number, yTop: number, wTop: number, xBottom: number, yBottom: number, wBottom: number, colour: string): void {
    const first = Math.round(yTop);
    const last = Math.round(yBottom);
    for (let row = Math.min(first, last); row <= Math.max(first, last); row++) {
      const along = last === first ? 0 : (row - first) / (last - first);
      const centre = xTop + (xBottom - xTop) * along;
      const width = Math.max(1, Math.round(wTop + (wBottom - wTop) * along));
      const left = Math.round(centre - (width - 1) / 2);
      for (let column = 0; column < width; column++) this.set(left + column, row, colour);
    }
  }

  disc(cx: number, cy: number, radius: number, colour: string): void {
    for (let y = Math.floor(cy - radius); y <= Math.ceil(cy + radius); y++) {
      for (let x = Math.floor(cx - radius); x <= Math.ceil(cx + radius); x++) if (Math.hypot(x - cx, y - cy) <= radius) this.set(x, y, colour);
    }
  }
}

function shoulderWidth(appearance: Appearance): number {
  switch (appearance.build) {
    case "lean":
      return 7;
    case "stocky":
      return 10;
    default:
      return 8;
  }
}

interface Paint {
  skin: string;
  hair: string;
  shirt: Kit;
  sleeve: string;
  trim: string;
  shorts: string;
  sock: string;
  keeper: boolean;
}

/** Shorts that stand out from the shirt: the kit's second colour unless it is too like the first. */
function shortsFor(kit: Kit): string {
  if (distance(kit.secondary, kit.primary) > 150) return kit.secondary;
  return distance(kit.primary, "#ffffff") > 300 ? "#f2f2f4" : "#1b1d22";
}

function paintOf(dress: FigureDress): Paint {
  const keeper = dress.keeper !== null;
  const skin = skinColour(dress.appearance);
  const hair = dress.appearance.hair_style === "bald" ? shade(skin, 0.86) : hairColour(dress.appearance);
  return {
    skin,
    hair,
    shirt: dress.keeper === null ? dress.kit : { pattern: "solid", primary: dress.keeper, secondary: dress.keeper },
    sleeve: dress.keeper ?? dress.kit.primary,
    trim: dress.keeper === null ? dress.kit.secondary : shade(dress.keeper, 0.7),
    shorts: keeper ? KEEPER_SHORTS : shortsFor(dress.kit),
    sock: keeper ? shade(dress.keeper ?? KEEPER_SHORTS, 0.55) : dress.kit.primary,
    keeper,
  };
}

function leg(raster: Raster, hip: { x: number; y: number }, joint: Leg, paint: Paint, far: boolean): void {
  const dim = far ? FAR_SHADE : 1;
  const kneeX = hip.x + THIGH * Math.sin(joint.a);
  const kneeY = hip.y + THIGH * Math.cos(joint.a);
  const shin = joint.a - joint.k;
  const ankleX = kneeX + SHIN * Math.sin(shin);
  const ankleY = kneeY + SHIN * Math.cos(shin);
  const sockFrom = 0.3;
  const toeX = ankleX + 5 * Math.cos(shin * 0.5);
  const toeY = ankleY - 5 * Math.sin(shin * 0.5) + 0.5;
  if (!far) {
    raster.taper(hip.x, hip.y, 7, kneeX, kneeY, 6, OUTLINE);
    raster.taper(kneeX, kneeY, 6, ankleX, ankleY, 5, OUTLINE);
    raster.line(ankleX, ankleY, toeX, toeY, 4, OUTLINE);
  }
  raster.taper(hip.x, hip.y, 5, kneeX, kneeY, 4, shade(paint.skin, dim));
  raster.taper(kneeX, kneeY, 4, ankleX, ankleY, 3, shade(paint.skin, dim));
  raster.taper(kneeX + (ankleX - kneeX) * sockFrom, kneeY + (ankleY - kneeY) * sockFrom, 4, ankleX, ankleY, 3, shade(paint.sock, dim));
  // A turn-over band at the top of the sock.
  raster.line(kneeX + (ankleX - kneeX) * sockFrom, kneeY + (ankleY - kneeY) * sockFrom, kneeX + (ankleX - kneeX) * (sockFrom + 0.1), kneeY + (ankleY - kneeY) * (sockFrom + 0.1), 4, shade(paint.trim, dim));
  raster.line(ankleX, ankleY, toeX, toeY, 3, shade(BOOT, dim));
  raster.set(ankleX + 1, ankleY + 1.6, shade(SOLE, dim));
  raster.set(toeX - 0.5, toeY + 1, shade(SOLE, dim));
}

function arm(raster: Raster, shoulder: { x: number; y: number }, joint: Arm, paint: Paint, far: boolean): void {
  const dim = far ? FAR_SHADE : 1;
  const elbowX = shoulder.x + UPPER_ARM * Math.sin(joint.c);
  const elbowY = shoulder.y + UPPER_ARM * Math.cos(joint.c);
  const fore = joint.c + joint.e;
  const handX = elbowX + FOREARM * Math.sin(fore);
  const handY = elbowY + FOREARM * Math.cos(fore);
  if (!far) {
    raster.line(elbowX, elbowY, handX, handY, 4, OUTLINE);
    raster.line(shoulder.x, shoulder.y, elbowX, elbowY, 5, OUTLINE);
  }
  raster.line(elbowX, elbowY, handX, handY, 2, shade(paint.skin, dim));
  raster.line(shoulder.x, shoulder.y, elbowX, elbowY, 3, shade(paint.sleeve, dim * 1.04));
  // A cuff in the trim colour where the sleeve ends.
  raster.line(elbowX - (elbowX - shoulder.x) * 0.2, elbowY - (elbowY - shoulder.y) * 0.2, elbowX, elbowY, 3, shade(paint.trim, dim));
  if (paint.keeper) raster.disc(handX, handY, 1.8, shade(GLOVE, dim));
}

/** Mix two colours: `amount` 0 is `a`, 1 is `b`. */
function mix(a: string, b: string, amount: number): string {
  const [ar, ag, ab] = hex(a);
  const [br, bg, bb] = hex(b);
  const part = (x: number, y: number): string => Math.round(x + (y - x) * amount).toString(16).padStart(2, "0");
  return `#${part(ar, br)}${part(ag, bg)}${part(ab, bb)}`;
}

/** The head: skin, a hair style that changes the silhouette, ear, brow, eye, nose, mouth and any beard. */
function head(raster: Raster, centre: { x: number; y: number }, appearance: Appearance, paint: Paint): void {
  const { x, y } = centre;
  const style = appearance.hair_style;
  const hair = paint.hair;
  const hairLight = mix(hair, "#ffffff", 0.32);
  const hairDark = shade(hair, 0.7);
  const scalp = mix(paint.skin, hair, 0.55);
  const puffy = style === "curly";
  raster.disc(x, y, puffy ? HEAD_RADIUS + 2.1 : HEAD_RADIUS + 0.7, OUTLINE);
  if (style === "long" || style === "braids") {
    raster.taper(x - 2.5, y - 2, 6, x - 4.2, y + 7.5, 5, OUTLINE);
    raster.taper(x - 2.5, y - 2, 4, x - 4.2, y + 7.5, 3, hair);
    if (style === "braids") for (let row = 0; row < 7; row += 2) raster.set(x - 3.2 - row * 0.15, y + row, hairDark);
  }
  if (puffy) raster.disc(x - 0.4, y - 0.8, HEAD_RADIUS + 1.4, hair);
  raster.disc(x, y, HEAD_RADIUS, paint.skin);
  if (style !== "bald") {
    const cropped = style === "buzz" || style === "fade";
    const fringe = cropped ? y - 2.4 : y - 1.2;
    const backEdge = style === "fade" ? x - 2.6 : cropped ? x - 1.2 : x - 1.4;
    for (let row = Math.floor(y - 7); row <= Math.ceil(y + 7); row++) {
      for (let column = Math.floor(x - 7); column <= Math.ceil(x + 7); column++) {
        if (raster.get(column, row) !== paint.skin) continue;
        const onTop = row < fringe;
        const behind = column < backEdge;
        if (!onTop && !behind) continue;
        let colour = row <= y - HEAD_RADIUS + 1.3 ? hairLight : hair;
        if (cropped) colour = style === "fade" && !onTop ? scalp : mix(paint.skin, hair, onTop ? 0.7 : 0.5);
        raster.set(column, row, colour);
      }
    }
    if (style === "short" || style === "long" || style === "braids") {
      raster.set(x + 2.4, fringe + 0.3, hair);
      raster.set(x + 3.4, fringe + 0.3, hair);
      raster.set(x + 1.4, fringe + 0.3, hair);
    }
    if (puffy) {
      raster.disc(x + 2, y + 1.3, 2.9, paint.skin);
      raster.set(x + 0.5, y - 5.2, hairLight);
      raster.set(x - 2.2, y - 4.4, hairLight);
      raster.set(x - 3.8, y - 1.8, hairDark);
    }
  } else {
    raster.set(x - 0.4, y - 3.2, shade(paint.skin, 1.35));
    raster.set(x + 0.6, y - 3.4, shade(paint.skin, 1.35));
  }
  raster.set(x - 0.4, y + 1, shade(paint.skin, 0.72));
  raster.set(x - 0.4, y + 2, shade(paint.skin, 0.8));
  const face = { x: x + 2.3, y };
  const brow = style === "bald" ? shade(paint.skin, 0.62) : hairDark;
  raster.set(face.x, face.y - 1.9, brow);
  raster.set(face.x + 1, face.y - 1.9, brow);
  raster.set(face.x, face.y - 0.7, WHITE);
  raster.set(face.x + 1, face.y - 0.7, EYE);
  raster.set(face.x, face.y + 0.3, EYE);
  raster.set(face.x + 1.9, face.y + 0.9, shade(paint.skin, 1.2));
  raster.set(face.x + 1, face.y + 2.7, shade(paint.skin, 0.58));
  const beardColour = shade(hair, 0.82);
  if (appearance.facial_hair === "beard" || appearance.facial_hair === "goatee") {
    const full = appearance.facial_hair === "beard";
    for (let row = Math.floor(y); row <= Math.ceil(y + HEAD_RADIUS + 1); row++) {
      for (let column = Math.floor(x - 3); column <= Math.ceil(x + HEAD_RADIUS + 1); column++) {
        if (raster.get(column, row) !== paint.skin) continue;
        const chin = row > y + 2.3 && (full || column > x + 1);
        const sideburn = full && column < x + 1 && row > y + 0.6;
        const cheek = full && row > y + 1.2 && column > x + 0.5;
        if (chin || sideburn || cheek) raster.set(column, row, beardColour);
      }
    }
    raster.set(face.x + 0.6, face.y + 1.8, beardColour);
    raster.set(face.x + 1.6, face.y + 1.8, beardColour);
    raster.set(face.x + 2.4, face.y + 1.8, beardColour);
  } else if (appearance.facial_hair === "stubble") {
    for (const [dx, dy] of [[1, 2.4], [2, 2.8], [3, 2.4], [1, 3.4], [2.2, 3.6], [0, 3], [3, 3.4], [0.4, 2], [3.2, 1.6]] as const) raster.set(x + dx, y + dy, mix(paint.skin, hair, 0.5));
  }
}

function shirt(raster: Raster, hip: { x: number; y: number }, shoulder: { x: number; y: number }, width: number, paint: Paint): void {
  const mark = "#shirt";
  // A trunk broader at the shoulders than at the waist.
  raster.trapezoid(shoulder.x, shoulder.y - 0.5, width, hip.x, hip.y - 0.5, width - 2, mark);
  const cells: number[] = [];
  raster.cells.forEach((cell, index) => {
    if (cell === mark) cells.push(index);
  });
  const columns = cells.map((index) => index % FIGURE_W);
  const rows = cells.map((index) => Math.floor(index / FIGURE_W));
  const left = Math.min(...columns);
  const top = Math.min(...rows);
  const bottom = Math.max(...rows);
  const wide = Math.max(...columns) - left + 1;
  const tall = bottom - top + 1;
  for (const index of cells) {
    const column = index % FIGURE_W;
    const row = Math.floor(index / FIGURE_W);
    const base = shirtColour(paint.shirt, Math.floor(((column - left) * 5) / wide), Math.floor(((row - top) * 3) / tall));
    // The back of the shirt (left) is in a little shade, the chest catches the light, the hem is darker.
    const lit = column - left >= wide - 2 ? 1.14 : column - left < 2 ? 0.84 : 1;
    raster.cells[index] = shade(base, row >= bottom ? lit * 0.78 : lit);
  }
  // A round collar in the trim colour at the neck.
  raster.set(shoulder.x + 0.5, shoulder.y - 0.8, paint.trim);
  raster.set(shoulder.x + 1.5, shoulder.y - 0.8, paint.trim);
  raster.set(shoulder.x - 0.5, shoulder.y - 0.8, paint.trim);
}

/** Paint one figure and outline it. */
function render(dress: FigureDress, pose: FigurePose, phase: number, amp: number): (string | null)[] {
  const raster = new Raster();
  const paint = paintOf(dress);
  const J = joints(pose, phase, amp);
  const width = shoulderWidth(dress.appearance);
  const hip = { x: FEET_X, y: FEET_Y - LEG_LENGTH + J.bob };
  const shoulder = { x: hip.x + TORSO * Math.sin(J.lean), y: hip.y - TORSO * Math.cos(J.lean) };
  const crown = { x: shoulder.x + 2.6 * Math.sin(J.lean * 0.6) + 1, y: shoulder.y - 1 - HEAD_RADIUS };
  arm(raster, { x: shoulder.x, y: shoulder.y + 1.2 }, J.farArm, paint, true);
  leg(raster, hip, J.far, paint, true);
  leg(raster, hip, J.near, paint, false);
  shirt(raster, hip, shoulder, width, paint);
  // Shorts: flared, in a colour that stands apart from the shirt, with a dark waistband line.
  raster.trapezoid(hip.x, hip.y, width - 2, hip.x, hip.y + 4, width, paint.shorts);
  raster.trapezoid(hip.x, hip.y, width - 2, hip.x, hip.y, width - 2, shade(paint.shorts, 0.55));
  raster.trapezoid(hip.x, hip.y + 4, width, hip.x, hip.y + 4, width, shade(paint.shorts, 0.78));
  raster.line(shoulder.x + 0.6, shoulder.y - 1, shoulder.x + 1, shoulder.y - 2.2, 3, paint.skin);
  head(raster, crown, dress.appearance, paint);
  arm(raster, { x: shoulder.x, y: shoulder.y + 1.2 }, J.nearArm, paint, false);
  const out = raster.cells.slice();
  for (let y = 0; y < FIGURE_H; y++) {
    for (let x = 0; x < FIGURE_W; x++) {
      if (raster.cells[y * FIGURE_W + x] !== null) continue;
      const touching = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => raster.get(x + (dx ?? 0), y + (dy ?? 0)) !== null);
      if (touching) out[y * FIGURE_W + x] = OUTLINE;
    }
  }
  return out;
}

const cache = new Map<string, HTMLCanvasElement>();

function lookKey(dress: FigureDress): string {
  const { kit, keeper, appearance } = dress;
  return [kit.pattern, kit.primary, kit.secondary, keeper, appearance.skin_tone, appearance.hair_colour, appearance.hair_style, appearance.facial_hair, appearance.build].join("|");
}

/** Frames in one stride cycle. */
export const STRIDE_STEPS = 8;

/** The cached sprite for a look, pose and stride phase (0 to 1) at a stride amplitude. */
export function figureSprite(dress: FigureDress, pose: FigurePose, phase: number, amp: number): HTMLCanvasElement {
  const step = Math.floor((((phase % 1) + 1) % 1) * STRIDE_STEPS);
  const key = `${lookKey(dress)}|${pose}|${pose === "run" || pose === "lean" ? `${step}|${amp}` : ""}`;
  const found = cache.get(key);
  if (found !== undefined) return found;
  const canvas = document.createElement("canvas");
  canvas.width = FIGURE_W;
  canvas.height = FIGURE_H;
  const ctx = canvas.getContext("2d");
  if (ctx !== null) {
    render(dress, pose, step / STRIDE_STEPS, amp).forEach((colour, index) => {
      if (colour === null) return;
      ctx.fillStyle = colour;
      ctx.fillRect(index % FIGURE_W, Math.floor(index / FIGURE_W), 1, 1);
    });
  }
  cache.set(key, canvas);
  return canvas;
}

export interface StrideGait {
  pose: FigurePose;
  /** Stride amplitude: how far the legs swing. */
  amp: number;
  /** Seconds for one full stride. */
  period: number;
}

/** How a player moves at a given speed (metres per second): stand, walk, jog, run or sprint. */
export function gaitFor(speed: number): StrideGait {
  if (speed < 0.4) return { pose: "stand", amp: 0, period: 1 };
  if (speed < 1.8) return { pose: "run", amp: 0.35, period: 0.95 };
  if (speed < 4) return { pose: "run", amp: 0.7, period: 0.62 };
  if (speed < 6.5) return { pose: "run", amp: 1, period: 0.5 };
  return { pose: "lean", amp: 1.2, period: 0.42 };
}
