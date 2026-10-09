import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { anchorPixels, ANCHOR_H, ANCHOR_W } from "./anchor.ts";
import { castLooks, lookFor, type AnchorFace } from "./anchor-look.ts";

const NEUTRAL: AnchorFace = { mouth: 0, blink: false, gaze: 0, brow: 0 };

/** The rows on which two grids differ. */
function differingRows(a: (string | null)[], b: (string | null)[]): number[] {
  const rows = new Set<number>();
  a.forEach((cell, index) => {
    if (cell !== b[index]) rows.add(Math.floor(index / ANCHOR_W));
  });
  return [...rows].sort((x, y) => x - y);
}

describe("anchor looks", () => {
  it("dresses the same speaker the same way every time", () => {
    assert.deepEqual(lookFor("med_00001", 0), lookFor("med_00001", 0));
  });

  it("gives different speakers different looks", () => {
    assert.notDeepEqual(lookFor("med_00001", 0).appearance, lookFor("med_00002", 0).appearance);
  });

  it("puts neighbours in different jackets", () => {
    const jackets = castLooks(["a", "b", "c", "d"]).map((look) => look.jacket);
    assert.equal(new Set(jackets).size, 4);
  });

  it("never gives two people at the desk the same hairstyle", () => {
    for (const ids of [["med_00001", "med_00002", "med_00004"], ["a", "b", "c", "d"], ["x", "y"]]) {
      const styles = castLooks(ids).map((look) => look.appearance.hair_style);
      assert.equal(new Set(styles).size, styles.length, `${ids}: ${styles}`);
    }
  });
});

describe("anchor pixels", () => {
  const look = lookFor("med_00002", 1);

  it("paints a sprite with a head, shoulders and an outline, inside its grid", () => {
    const grid = anchorPixels(look, NEUTRAL);
    assert.equal(grid.cells.length, ANCHOR_W * ANCHOR_H);
    assert.ok(grid.cells.filter((cell) => cell !== null).length > 1200);
    assert.ok(grid.get(32, 3) !== null || grid.get(32, 2) !== null, "no crown");
    assert.ok(grid.get(32, ANCHOR_H - 1) !== null, "body does not reach the desk");
    assert.equal(grid.get(0, 0), null);
  });

  it("is the same picture every time for the same face", () => {
    assert.deepEqual(anchorPixels(look, NEUTRAL).cells, anchorPixels(look, NEUTRAL).cells);
  });

  it("changes only the mouth when the mouth opens", () => {
    const rows = differingRows(anchorPixels(look, NEUTRAL).cells, anchorPixels(look, { ...NEUTRAL, mouth: 3 }).cells);
    assert.ok(rows.length > 0);
    assert.ok(rows.every((row) => row >= 23 && row <= 29), `rows ${rows}`);
  });

  it("changes only the eyes when they blink or look aside", () => {
    for (const face of [{ ...NEUTRAL, blink: true }, { ...NEUTRAL, gaze: 1 as const }, { ...NEUTRAL, gaze: -1 as const }]) {
      const rows = differingRows(anchorPixels(look, NEUTRAL).cells, anchorPixels(look, face).cells);
      assert.ok(rows.length > 0);
      assert.ok(rows.every((row) => row >= 16 && row <= 18), `rows ${rows}`);
    }
  });

  it("raises the brows without touching the rest of the face", () => {
    const rows = differingRows(anchorPixels(look, NEUTRAL).cells, anchorPixels(look, { ...NEUTRAL, brow: 1 }).cells);
    assert.ok(rows.length > 0);
    assert.ok(rows.every((row) => row >= 13 && row <= 15), `rows ${rows}`);
  });

  it("draws every hairstyle, facial hair and build without leaving the grid", () => {
    const styles = ["short", "buzz", "fade", "curly", "long", "braids", "bald"];
    for (const hair_style of styles) {
      for (const facial_hair of ["none", "stubble", "beard", "goatee"]) {
        for (const build of ["lean", "average", "stocky"]) {
          const base = lookFor("t", 0);
          const grid = anchorPixels({ ...base, appearance: { ...base.appearance, hair_style, facial_hair, build } }, { ...NEUTRAL, mouth: 2 });
          assert.ok(grid.cells.some((cell) => cell !== null));
          // The outline ring means the outermost columns stay clear.
          for (let y = 0; y < ANCHOR_H; y += 1) assert.equal(grid.get(0, y), null, `${hair_style}/${build} touches the left edge`);
        }
      }
    }
  });
});
