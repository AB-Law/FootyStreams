import type { AnchorFace, AnchorLook } from "./anchor-look.ts";
import { mix, shade } from "./figure.ts";
import { hairColour, skinColour } from "./palette.ts";
import { PixelGrid } from "./pixelgrid.ts";

// A news anchor seen from the front, from the crown to the belt: head, hair, face, collar and jacket,
// painted pixel by pixel and ringed in a dark outline. The desk hides the lower part of the jacket.
// Light comes from the upper left, so the right side of everything is a little darker.

export const ANCHOR_W = 64;
export const ANCHOR_H = 60;
/** Column of the face's centre line. */
const CX = 32;
const HEAD_TOP = 4;
/** Half the head's width on each row from the crown down: a rounded skull tapering to a square jaw. */
const HEAD_HALF = [4, 7, 8, 9, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10, 10, 9, 9, 8, 7, 6, 5, 4, 3] as const;
const SHOULDER_TOP = 34;
const SHOULDERS: Record<string, number> = { lean: 20, stocky: 26 };
const AVERAGE_SHOULDERS = 23;
const OUTLINE = "#12151c";
const EYE_DARK = "#1b1512";
const WHITE = "#f4f2ec";

interface Tones {
  skin: string;
  light: string;
  mid: string;
  shade: string;
  deep: string;
  hair: string;
  hairLight: string;
  hairDark: string;
  lip: string;
  lipDark: string;
  jacket: string;
  jacketLight: string;
  jacketShade: string;
  jacketDeep: string;
  shirt: string;
  shirtShade: string;
}

function tonesOf(look: AnchorLook): Tones {
  const skin = skinColour(look.appearance);
  const hair = look.appearance.hair_style === "bald" ? shade(skin, 0.86) : hairColour(look.appearance);
  return {
    skin,
    light: shade(skin, 1.12),
    mid: shade(skin, 0.92),
    shade: shade(skin, 0.8),
    deep: shade(skin, 0.64),
    hair,
    hairLight: mix(hair, "#ffffff", 0.3),
    hairDark: shade(hair, 0.66),
    lip: mix(skin, "#b84a4a", 0.5),
    lipDark: mix(skin, "#7a2a2a", 0.6),
    jacket: look.jacket,
    jacketLight: shade(look.jacket, 1.22),
    jacketShade: shade(look.jacket, 0.76),
    jacketDeep: shade(look.jacket, 0.56),
    shirt: "#eceef2",
    shirtShade: "#c9cfd8",
  };
}

const hairHalf = (y: number): number => (y < HEAD_TOP ? ({ 2: 3, 3: 5 } as Record<number, number>)[y] ?? -1 : y === HEAD_TOP ? 7 : (HEAD_HALF[y - HEAD_TOP] ?? -2) + 1);

function paintTorso(grid: PixelGrid, look: AnchorLook, c: Tones): void {
  const reach = SHOULDERS[look.appearance.build] ?? AVERAGE_SHOULDERS;
  for (let y = SHOULDER_TOP; y < ANCHOR_H; y += 1) {
    const half = Math.min(reach, 5 + Math.round(Math.sqrt(y - SHOULDER_TOP) * 7));
    for (let x = CX - half; x <= CX + half; x += 1) {
      const across = x - CX;
      grid.set(x, y, across > reach - 7 ? c.jacketShade : across < -(reach - 5) ? c.jacketLight : c.jacket);
    }
  }
  for (let y = SHOULDER_TOP; y <= 48; y += 1) {
    const v = Math.max(1, 6 - Math.floor((y - SHOULDER_TOP) * 0.45));
    grid.row(CX - v - 3, CX - v - 1, y, c.jacketLight);
    grid.row(CX + v + 1, CX + v + 3, y, c.jacket);
    grid.set(CX - v - 1, y, c.jacketDeep);
    grid.set(CX + v + 1, y, c.jacketDeep);
    grid.row(CX - v, CX + v, y, look.tie ? c.shirt : look.accent);
    grid.row(CX + 1, CX + v, y, look.tie ? c.shirtShade : shade(look.accent, 0.82));
  }
  grid.rect(CX + 12, 44, 5, 1, c.jacketDeep);
  grid.row(CX + 13, CX + 15, 43, look.accent);
  grid.rect(CX - 6, 42, 2, 3, "#101216");
  grid.set(CX - 6, 42, "#7d8aa0");
}

function paintTie(grid: PixelGrid, look: AnchorLook): void {
  if (!look.tie) {
    for (let y = SHOULDER_TOP; y <= 38; y += 1) grid.row(CX - (38 - y) / 2 - 1, CX + (38 - y) / 2 + 1, y, shade(skinColour(look.appearance), 0.9));
    return;
  }
  grid.row(CX - 1, CX + 1, 36, shade(look.accent, 1.15));
  grid.row(CX - 1, CX + 1, 37, look.accent);
  for (let y = 38; y < ANCHOR_H; y += 1) {
    const wide = y >= 41 ? 2 : 1;
    for (let x = CX - wide; x <= CX + wide; x += 1) {
      const stripe = (y + x) % 5 === 0;
      grid.set(x, y, x > CX ? shade(look.accent, 0.7) : stripe ? shade(look.accent, 1.3) : look.accent);
    }
  }
}

function paintNeck(grid: PixelGrid, look: AnchorLook, c: Tones): void {
  const half = look.appearance.build === "stocky" ? 5 : look.appearance.build === "lean" ? 3 : 4;
  for (let y = 28; y <= 35; y += 1) grid.row(CX - half, CX + half, y, y <= 30 ? c.shade : y <= 31 ? c.mid : c.skin);
  grid.row(CX + half, CX + half, 33, c.shade);
  // Collar points on each side of the neck.
  for (let y = 33; y <= 36; y += 1) {
    grid.row(CX - half - 3 + (y - 33), CX - half - 1, y, c.shirt);
    grid.row(CX + half + 1, CX + half + 3 - (y - 33), y, c.shirtShade);
  }
}

function paintHead(grid: PixelGrid, c: Tones): void {
  HEAD_HALF.forEach((half, index) => {
    const y = HEAD_TOP + index;
    for (let x = CX - half; x <= CX + half; x += 1) {
      const u = (x - CX) / half;
      let colour = c.skin;
      if (u > 0.7 || (y >= 27 && u > 0.35)) colour = c.shade;
      else if (u > 0.42) colour = c.mid;
      else if (u < -0.3 && u > -0.75 && y >= 9 && y <= 21) colour = c.light;
      else if (y >= 28) colour = c.mid;
      grid.set(x, y, colour);
    }
  });
  for (const side of [-1, 1] as const) {
    const x = CX + side * 12;
    grid.rect(Math.min(x, x + side), 15, 2, 5, c.mid);
    grid.set(x + (side > 0 ? 0 : 1), 17, c.shade);
  }
}

/** Is there hair at this pixel for the style? Rows above the hairline, plus sideburns. */
function hairAt(style: string, x: number, y: number): boolean {
  const reach = hairHalf(y);
  const side = Math.abs(x - CX);
  if (reach < 0 || side > reach) return false;
  switch (style) {
    case "bald":
      return false;
    case "buzz":
      return y < (side >= 9 ? 12 : 8) && side <= (HEAD_HALF[y - HEAD_TOP] ?? 3);
    case "fade":
      return y < (side >= 9 ? 11 : 8) && side <= (HEAD_HALF[y - HEAD_TOP] ?? 3);
    case "curly": {
      const dx = (x - CX) / 14.5;
      const dy = (y - 9) / 10;
      return dx * dx + dy * dy <= 1 && y < (side >= 11 ? 18 : side >= 8 ? 12 : 8);
    }
    case "long":
    case "braids":
      return y < (side >= 11 ? 19 : side >= 9 ? 14 : side >= 7 ? 11 : side <= 1 ? 8 : 10);
    default:
      return y < (side >= 11 ? 19 : side >= 10 ? 14 : side >= 8 ? 12 : x < CX + 3 ? 11 : 9);
  }
}

function paintHair(grid: PixelGrid, style: string, c: Tones): void {
  const cropped = style === "buzz" || style === "fade";
  for (let y = 0; y < 22; y += 1) {
    for (let x = CX - 15; x <= CX + 15; x += 1) {
      if (!hairAt(style, x, y)) continue;
      let colour = y <= 5 ? c.hairLight : c.hair;
      if (cropped) colour = mix(c.skin, c.hair, y < 8 ? 0.72 : 0.45);
      else if (style === "curly") colour = (x * 7 + y * 13) % 5 === 0 ? c.hairLight : (x * 5 + y * 3) % 7 === 1 ? c.hairDark : c.hair;
      else if ((style === "short" && x === CX + 3 && y >= 5 && y <= 9) || (hairAt(style, x, y) && !hairAt(style, x, y + 1) && y > 8 && Math.abs(x - CX) < 9)) colour = c.hairDark;
      grid.set(x, y, colour);
    }
  }
  if (style === "bald") {
    grid.row(CX - 4, CX - 2, 6, c.light);
    grid.row(CX - 3, CX - 1, 7, shade(c.skin, 1.2));
  }
}

/** Hair that hangs behind the neck (long styles), painted before the body. */
function paintHairBehind(grid: PixelGrid, style: string, c: Tones): void {
  if (style !== "long" && style !== "braids") return;
  for (let y = 8; y < 42; y += 1) grid.row(CX - 13, CX + 13, y, c.hairDark);
}

/** Long hair falling forward over the shoulders, painted after the body. */
function paintHairFront(grid: PixelGrid, style: string, c: Tones): void {
  if (style !== "long" && style !== "braids") return;
  for (const side of [-1, 1] as const) {
    for (let y = 14; y < 50; y += 1) {
      const sway = y > 30 ? Math.floor((y - 30) / 6) : 0;
      for (let step = 0; step < 4; step += 1) {
        const x = CX + side * (10 + step + sway);
        let colour = step === 3 ? c.hairDark : side < 0 && step === 0 ? c.hairLight : c.hair;
        if (style === "braids") colour = (y + step) % 3 === 0 ? c.hairDark : step === 1 ? c.hairLight : c.hair;
        grid.set(x, y, colour);
      }
    }
  }
}

function paintBrowsAndEyes(grid: PixelGrid, look: AnchorLook, face: AnchorFace, c: Tones): void {
  const brow = look.appearance.hair_style === "bald" ? c.deep : c.hairDark;
  const browY = face.brow === 1 ? 13 : 14;
  for (const side of [-1, 1] as const) {
    const near = side < 0 ? CX - 7 : CX + 4;
    grid.row(near - 1, near + 4, browY, brow);
    grid.row(side < 0 ? near - 1 : near + 4, side < 0 ? near - 1 : near + 4, browY + 1, brow);
    grid.row(near, near + 3, 16, c.deep);
    if (face.blink) {
      grid.row(near, near + 3, 17, c.deep);
      grid.row(near, near + 3, 18, c.shade);
      continue;
    }
    const iris = near + 1 + face.gaze;
    grid.row(near, near + 3, 17, WHITE);
    grid.row(near, near + 3, 18, c.mid);
    grid.rect(iris, 17, 2, 2, EYE_DARK);
    grid.set(iris, 17, "#4a3a30");
  }
}

function paintNose(grid: PixelGrid, c: Tones): void {
  grid.rect(CX, 19, 1, 3, c.light);
  grid.rect(CX + 1, 19, 1, 3, c.shade);
  grid.set(CX - 1, 22, c.shade);
  grid.set(CX + 1, 22, c.deep);
  grid.set(CX, 22, c.mid);
}

function paintFacialHair(grid: PixelGrid, style: string, c: Tones): void {
  const beard = shade(c.hair, 0.85);
  const stubble = mix(c.skin, c.hair, 0.4);
  HEAD_HALF.forEach((half, index) => {
    const y = HEAD_TOP + index;
    for (let x = CX - half; x <= CX + half; x += 1) {
      const side = Math.abs(x - CX);
      if (style === "beard" && (y >= 23 || (y === 22 && side >= 5) || (y >= 17 && side >= half - 1))) grid.set(x, y, (x + y) % 6 === 0 ? c.hairDark : beard);
      if (style === "goatee" && ((y >= 26 && side <= 3) || (y === 23 && side >= 2 && side <= 5))) grid.set(x, y, beard);
      if (style === "stubble" && y >= 21 && (x + y) % 2 === 0 && !(y >= 23 && y <= 26 && side <= 4)) grid.set(x, y, stubble);
    }
  });
}

function paintMouth(grid: PixelGrid, mouth: AnchorFace["mouth"], c: Tones): void {
  const teeth = "#f4f1ea";
  const inside = "#3a1414";
  if (mouth === 0) {
    grid.row(CX - 3, CX + 3, 24, c.lipDark);
    grid.row(CX - 2, CX + 2, 25, c.lip);
    grid.set(CX - 4, 23, c.shade);
    grid.set(CX + 4, 23, c.shade);
    return;
  }
  grid.row(CX - 3, CX + 3, 24, c.lipDark);
  if (mouth === 1) {
    grid.row(CX - 2, CX + 2, 25, inside);
    grid.row(CX - 2, CX + 2, 26, c.lip);
  } else if (mouth === 2) {
    grid.row(CX - 2, CX + 2, 25, teeth);
    grid.row(CX - 2, CX + 2, 26, inside);
    grid.row(CX - 2, CX + 2, 27, c.lip);
  } else {
    grid.row(CX - 3, CX + 3, 25, teeth);
    grid.rect(CX - 3, 26, 7, 2, inside);
    grid.row(CX - 1, CX + 1, 27, "#c4605a");
    grid.row(CX - 2, CX + 2, 28, c.lip);
  }
}

function paintGlasses(grid: PixelGrid): void {
  const frame = "#1a1a22";
  for (const left of [CX - 9, CX + 3]) {
    grid.row(left, left + 6, 15, frame);
    grid.row(left, left + 6, 19, frame);
    grid.rect(left, 16, 1, 3, frame);
    grid.rect(left + 6, 16, 1, 3, frame);
  }
  grid.row(CX - 2, CX + 2, 16, frame);
  grid.row(CX - 12, CX - 10, 16, frame);
  grid.row(CX + 10, CX + 12, 16, frame);
}

/** The pixels of one anchor with the given face. Pure, so it can be tested without a canvas. */
export function anchorPixels(look: AnchorLook, face: AnchorFace): PixelGrid {
  const grid = new PixelGrid(ANCHOR_W, ANCHOR_H);
  const c = tonesOf(look);
  const style = look.appearance.hair_style;
  paintHairBehind(grid, style, c);
  paintTorso(grid, look, c);
  paintNeck(grid, look, c);
  paintTie(grid, look);
  paintHead(grid, c);
  paintHair(grid, style, c);
  paintBrowsAndEyes(grid, look, face, c);
  paintNose(grid, c);
  paintFacialHair(grid, look.appearance.facial_hair, c);
  paintMouth(grid, face.mouth, c);
  if (look.glasses) paintGlasses(grid);
  paintHairFront(grid, style, c);
  grid.outline(OUTLINE);
  return grid;
}

const cache = new Map<string, HTMLCanvasElement>();

/** The cached sprite for a look and face. */
export function anchorSprite(look: AnchorLook, face: AnchorFace): HTMLCanvasElement {
  const key = `${JSON.stringify(look)}|${face.mouth}${face.blink ? "b" : "o"}${face.gaze}${face.brow}`;
  const found = cache.get(key);
  if (found !== undefined) return found;
  const sprite = anchorPixels(look, face).toCanvas();
  cache.set(key, sprite);
  return sprite;
}
