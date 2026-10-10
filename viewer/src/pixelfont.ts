// A proportional pixel font with lower case, for the news desk (font.ts is a 3x5 upper-case font for
// the pitch). Capitals are 7 rows tall, small letters sit on rows 2-6 and descenders run down to row 8.
// Each glyph is `[top, ...rows]`: `top` is the row of its first line, "#" is a lit pixel. Glyphs are
// trimmed to their ink, so "i" is one pixel wide and "m" is five.

type Glyph = readonly [top: number, ...rows: string[]];

const GLYPHS: Record<string, Glyph> = {
  A: [0, ".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  B: [0, "####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
  C: [0, ".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
  D: [0, "####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
  E: [0, "#####", "#....", "#....", "####.", "#....", "#....", "#####"],
  F: [0, "#####", "#....", "#....", "####.", "#....", "#....", "#...."],
  G: [0, ".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
  H: [0, "#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  I: [0, "###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
  J: [0, "..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
  K: [0, "#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
  L: [0, "#....", "#....", "#....", "#....", "#....", "#....", "#####"],
  M: [0, "#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
  N: [0, "#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"],
  O: [0, ".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  P: [0, "####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
  Q: [0, ".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
  R: [0, "####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
  S: [0, ".####", "#....", "#....", ".###.", "....#", "....#", "####."],
  T: [0, "#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
  U: [0, "#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  V: [0, "#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
  W: [0, "#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
  X: [0, "#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
  Y: [0, "#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
  Z: [0, "#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
  a: [2, ".###.", "....#", ".####", "#...#", ".####"],
  b: [0, "#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
  c: [2, ".###.", "#...#", "#....", "#...#", ".###."],
  d: [0, "....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
  e: [2, ".###.", "#...#", "#####", "#....", ".###."],
  f: [0, "..##.", ".#..#", ".#...", "###..", ".#...", ".#...", ".#..."],
  g: [2, ".####", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
  h: [0, "#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
  i: [0, "#", ".", "#", "#", "#", "#", "#"],
  j: [0, "..#", "...", "..#", "..#", "..#", "..#", "..#", "#.#", ".#."],
  k: [0, "#...", "#...", "#..#", "#.#.", "##..", "#.#.", "#..#"],
  l: [0, "##.", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
  m: [2, "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"],
  n: [2, "####.", "#...#", "#...#", "#...#", "#...#"],
  o: [2, ".###.", "#...#", "#...#", "#...#", ".###."],
  p: [2, "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."],
  q: [2, ".####", "#...#", "#...#", "#...#", ".####", "....#", "....#"],
  r: [2, "#.##", "##..", "#...", "#...", "#..."],
  s: [2, ".####", "#....", ".###.", "....#", "####."],
  t: [1, ".#..", "###.", ".#..", ".#..", ".#.#", "..#."],
  u: [2, "#...#", "#...#", "#...#", "#..##", ".##.#"],
  v: [2, "#...#", "#...#", "#...#", ".#.#.", "..#.."],
  w: [2, "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."],
  x: [2, "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
  y: [2, "#...#", "#...#", "#...#", ".####", "....#", "#...#", ".###."],
  z: [2, "#####", "...#.", "..#..", ".#...", "#####"],
  "0": [0, ".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
  "1": [0, "..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
  "2": [0, ".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
  "3": [0, ".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
  "4": [0, "...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
  "5": [0, "#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
  "6": [0, "..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
  "7": [0, "#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
  "8": [0, ".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
  "9": [0, ".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
  ".": [6, "#"],
  ",": [6, ".#", "#."],
  "!": [0, "#", "#", "#", "#", "#", ".", "#"],
  "?": [0, ".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
  ":": [3, "#", ".", ".", "#"],
  ";": [3, "#", ".", ".", "#", "#"],
  "-": [4, "###"],
  "–": [4, "####"],
  "'": [0, "#", "#"],
  '"': [0, "#.#", "#.#"],
  "(": [0, ".#", "#.", "#.", "#.", "#.", "#.", ".#"],
  ")": [0, "#.", ".#", ".#", ".#", ".#", ".#", "#."],
  "%": [0, "##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"],
  "/": [0, "....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
  "+": [3, ".#.", "###", ".#."],
  "&": [0, ".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
  "·": [4, "##", "##"],
  "…": [6, "#.#.#"],
};

const SPACE_ADVANCE = 4;
/** Rows from the top of a capital to the bottom of a descender, and the gap that reads well between lines. */
export const GLYPH_HEIGHT = 9;
export const LINE_PITCH = 11;

/** What the font has no glyph for, folded to the nearest thing it does have. */
const FOLD: Record<string, string> = {
  ß: "ss", æ: "ae", Æ: "AE", œ: "oe", Œ: "OE", ø: "o", Ø: "O", đ: "d", Đ: "D", ł: "l", Ł: "L",
  "’": "'", "‘": "'", "“": '"', "”": '"', "—": "–", "−": "-", "‑": "-", " ": " ", "\t": " ",
};

interface Compiled {
  width: number;
  points: readonly (readonly [number, number])[];
}

function compile([top, ...rows]: Glyph): Compiled {
  const lit: [number, number][] = [];
  rows.forEach((row, index) => {
    [...row].forEach((cell, column) => {
      if (cell === "#") lit.push([column, top + index]);
    });
  });
  const left = Math.min(...lit.map(([column]) => column));
  const right = Math.max(...lit.map(([column]) => column));
  return { width: right - left + 1, points: lit.map(([column, row]) => [column - left, row] as const) };
}

const COMPILED = new Map<string, Compiled>(Object.entries(GLYPHS).map(([char, glyph]) => [char, compile(glyph)]));
const UNKNOWN = COMPILED.get("?") as Compiled;

/** Accents removed, look-alikes folded, whitespace collapsed to plain spaces. Case is kept. */
export function foldText(text: string): string {
  const plain = text.normalize("NFD").replace(/\p{M}/gu, "");
  return [...plain].map((char) => FOLD[char] ?? char).join("");
}

/** Whether the font draws `char` as itself rather than as a question mark. */
export function hasGlyph(char: string): boolean {
  return COMPILED.has(char);
}

function glyphFor(char: string): Compiled {
  return COMPILED.get(char) ?? UNKNOWN;
}

function advance(char: string): number {
  return char === " " ? SPACE_ADVANCE : glyphFor(char).width + 1;
}

/** Width in pixels of `text` at `scale` (no trailing gap). */
export function textWidth(text: string, scale = 1): number {
  const total = [...foldText(text)].reduce((sum, char) => sum + advance(char), 0);
  return Math.max(total - 1, 0) * scale;
}

/** Draw `text` with its top-left at (x, y). */
export function drawText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, colour: string, scale = 1): void {
  ctx.fillStyle = colour;
  let cursor = x;
  for (const char of foldText(text)) {
    if (char !== " ") {
      for (const [column, row] of glyphFor(char).points) ctx.fillRect(cursor + column * scale, y + row * scale, scale, scale);
    }
    cursor += advance(char) * scale;
  }
}

/** Text with a hard one-pixel shadow down and to the right, so it reads on any backdrop. */
export function drawShadowed(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, colour: string, shadow: string, scale = 1): void {
  drawText(ctx, text, x + scale, y + scale, shadow, scale);
  drawText(ctx, text, x, y, colour, scale);
}

/** Greedy word wrap to `maxWidth` pixels. A word longer than a line is broken where it overflows. */
export function wrapText(text: string, maxWidth: number, scale = 1): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of foldText(text).split(/\s+/).filter(Boolean)) {
    const joined = line === "" ? word : `${line} ${word}`;
    if (textWidth(joined, scale) <= maxWidth) {
      line = joined;
      continue;
    }
    if (line !== "") lines.push(line);
    line = "";
    for (const char of word) {
      if (line !== "" && textWidth(line + char, scale) > maxWidth) {
        lines.push(line);
        line = "";
      }
      line += char;
    }
  }
  if (line !== "") lines.push(line);
  return lines;
}

/** `text` cut to fit `maxWidth` pixels, ending in an ellipsis if anything was left out. */
export function clipText(text: string, maxWidth: number, scale = 1): string {
  const plain = foldText(text);
  if (textWidth(plain, scale) <= maxWidth) return plain;
  let cut = plain;
  while (cut.length > 0 && textWidth(`${cut}…`, scale) > maxWidth) cut = cut.slice(0, -1);
  return `${cut.trimEnd()}…`;
}
