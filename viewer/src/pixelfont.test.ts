import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { drawText, foldText, GLYPH_HEIGHT, hasGlyph, textWidth, wrapText } from "./pixelfont.ts";

function rectsOf(text: string, scale = 1): number[][] {
  const rects: number[][] = [];
  const ctx = { fillStyle: "", fillRect: (x: number, y: number, w: number, h: number) => rects.push([x, y, w, h]) };
  drawText(ctx as unknown as CanvasRenderingContext2D, text, 0, 0, "#fff", scale);
  return rects;
}

describe("pixel font", () => {
  it("has a glyph for every letter, digit and mark a script uses", () => {
    const wanted = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?:;-–'\"()%/&+·…";
    for (const char of wanted) assert.ok(hasGlyph(char), `missing glyph for ${char}`);
  });

  it("folds accents and look-alikes but keeps case", () => {
    assert.equal(foldText("Gathiški Ælf"), "Gathiski AElf");
    assert.equal(foldText("Chille-Jaichàult"), "Chille-Jaichault");
    assert.equal(foldText("it’s “fine” — ok"), "it's \"fine\" – ok");
  });

  it("is proportional: narrow letters take less room", () => {
    assert.equal(textWidth("i"), 1);
    assert.equal(textWidth("Hi"), 7);
    assert.equal(textWidth("i i"), 7);
    assert.ok(textWidth("illi") < textWidth("MMMM"));
    assert.equal(textWidth("Hi", 2), 14);
  });

  it("draws inside its own measured width and the glyph height", () => {
    const rects = rectsOf("Hgjpqy,Q");
    const right = Math.max(...rects.map(([x, , w]) => (x ?? 0) + (w ?? 0)));
    const bottom = Math.max(...rects.map(([, y, , h]) => (y ?? 0) + (h ?? 0)));
    assert.ok(right <= textWidth("Hgjpqy,Q"));
    assert.ok(bottom <= GLYPH_HEIGHT);
  });

  it("draws whole pixels at any scale", () => {
    for (const rect of rectsOf("Pixel 42!", 3)) assert.ok(rect.every(Number.isInteger));
  });

  it("wraps to the width without losing words", () => {
    const text = "Good evening from the VPL News desk and welcome to a very long night of football";
    const lines = wrapText(text, 120);
    assert.ok(lines.length > 1);
    for (const line of lines) assert.ok(textWidth(line) <= 120, line);
    assert.equal(lines.join(" "), text);
  });

  it("breaks a word that is longer than a line", () => {
    const lines = wrapText("Supercalifragilisticexpialidocious", 60);
    assert.ok(lines.length > 1);
    for (const line of lines) assert.ok(textWidth(line) <= 60);
    assert.equal(lines.join(""), "Supercalifragilisticexpialidocious");
  });

  it("wraps nothing to nothing", () => {
    assert.deepEqual(wrapText("   ", 100), []);
  });
});
