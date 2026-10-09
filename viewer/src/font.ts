// A 3x5 pixel font, so text stays crisp at 320x226 (canvas text would be anti-aliased).
// Each glyph is five rows of three characters, "#" for a lit pixel.

const GLYPH_ROWS = 5;
const GLYPH_COLUMNS = 3;
const ADVANCE = GLYPH_COLUMNS + 1;

const GLYPHS: Record<string, readonly string[]> = {
  A: [".#.", "#.#", "###", "#.#", "#.#"],
  B: ["##.", "#.#", "##.", "#.#", "##."],
  C: [".##", "#..", "#..", "#..", ".##"],
  D: ["##.", "#.#", "#.#", "#.#", "##."],
  E: ["###", "#..", "##.", "#..", "###"],
  F: ["###", "#..", "##.", "#..", "#.."],
  G: [".##", "#..", "#.#", "#.#", ".##"],
  H: ["#.#", "#.#", "###", "#.#", "#.#"],
  I: ["###", ".#.", ".#.", ".#.", "###"],
  J: ["..#", "..#", "..#", "#.#", ".#."],
  K: ["#.#", "#.#", "##.", "#.#", "#.#"],
  L: ["#..", "#..", "#..", "#..", "###"],
  M: ["#.#", "###", "###", "#.#", "#.#"],
  N: ["##.", "#.#", "#.#", "#.#", "#.#"],
  O: [".#.", "#.#", "#.#", "#.#", ".#."],
  P: ["##.", "#.#", "##.", "#..", "#.."],
  Q: [".#.", "#.#", "#.#", "###", ".##"],
  R: ["##.", "#.#", "##.", "#.#", "#.#"],
  S: [".##", "#..", ".#.", "..#", "##."],
  T: ["###", ".#.", ".#.", ".#.", ".#."],
  U: ["#.#", "#.#", "#.#", "#.#", "###"],
  V: ["#.#", "#.#", "#.#", "#.#", ".#."],
  W: ["#.#", "#.#", "###", "###", "#.#"],
  X: ["#.#", "#.#", ".#.", "#.#", "#.#"],
  Y: ["#.#", "#.#", ".#.", ".#.", ".#."],
  Z: ["###", "..#", ".#.", "#..", "###"],
  "0": ["###", "#.#", "#.#", "#.#", "###"],
  "1": [".#.", "##.", ".#.", ".#.", "###"],
  "2": ["##.", "..#", ".#.", "#..", "###"],
  "3": ["##.", "..#", ".#.", "..#", "##."],
  "4": ["#.#", "#.#", "###", "..#", "..#"],
  "5": ["###", "#..", "##.", "..#", "##."],
  "6": [".##", "#..", "###", "#.#", "###"],
  "7": ["###", "..#", ".#.", ".#.", ".#."],
  "8": ["###", "#.#", "###", "#.#", "###"],
  "9": ["###", "#.#", "###", "..#", "##."],
  ":": ["...", ".#.", "...", ".#.", "..."],
  "+": ["...", ".#.", "###", ".#.", "..."],
  "-": ["...", "...", "###", "...", "..."],
  ".": ["...", "...", "...", "...", ".#."],
  "!": [".#.", ".#.", ".#.", "...", ".#."],
  "'": [".#.", ".#.", "...", "...", "..."],
  "?": ["##.", "..#", ".#.", "...", ".#."],
  " ": ["...", "...", "...", "...", "..."],
};

/** Upper case, accents removed (the names in the world carry them), unknown characters as "?". */
export function normalise(text: string): string {
  const plain = text.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
  return [...plain].map((char) => (char in GLYPHS ? char : "?")).join("");
}

export function textWidth(text: string, scale = 1): number {
  return Math.max(normalise(text).length * ADVANCE - 1, 0) * scale;
}

export function drawText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  colour: string,
  scale = 1,
): void {
  ctx.fillStyle = colour;
  let cursor = x;
  for (const char of normalise(text)) {
    const rows = GLYPHS[char] ?? GLYPHS["?"] ?? [];
    for (let row = 0; row < GLYPH_ROWS; row++) {
      for (let column = 0; column < GLYPH_COLUMNS; column++) {
        if (rows[row]?.[column] === "#") ctx.fillRect(cursor + column * scale, y + row * scale, scale, scale);
      }
    }
    cursor += ADVANCE * scale;
  }
}

/** Text centred on `centreX`, with a one-pixel dark outline for legibility on the pitch. */
export function drawCentred(
  ctx: CanvasRenderingContext2D,
  text: string,
  centreX: number,
  y: number,
  colour: string,
  scale = 1,
): void {
  const x = Math.round(centreX - textWidth(text, scale) / 2);
  for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1]] as const) drawText(ctx, text, x + dx * scale, y + dy * scale, "#101418", scale);
  drawText(ctx, text, x, y, colour, scale);
}
