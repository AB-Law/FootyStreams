import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { BUBBLE_LINES, paginate, typedAt } from "./bubble.ts";
import { textWidth } from "./pixelfont.ts";

const SHORT = "Opposite them, Bukach Harriers, out of Bukach.";
const LONG = "The desk has a great deal to say about this one, starting with how the home side set up and ending with who was named player of the match. ".repeat(3).trim();

describe("paginate", () => {
  it("keeps a short line on one page", () => {
    assert.equal(paginate(SHORT, 300).length, 1);
  });

  it("splits a long line into evenly filled pages that fit the bubble", () => {
    const pages = paginate(LONG, 200);
    assert.ok(pages.length > 1);
    for (const page of pages) {
      assert.ok(page.length <= BUBBLE_LINES);
      for (const line of page) assert.ok(textWidth(line) <= 200);
    }
    const sizes = pages.map((page) => page.length);
    assert.ok(Math.max(...sizes) - Math.min(...sizes) <= 1, `uneven pages ${sizes}`);
  });

  it("has no pages for no text", () => {
    assert.deepEqual(paginate("", 200), []);
  });
});

describe("typedAt", () => {
  const pages = paginate(SHORT, 300);
  const total = pages.flat().join("").length;

  it("starts empty and speaking", () => {
    const start = typedAt(pages, 0, 12);
    assert.equal(start.shown, 0);
    assert.ok(start.speaking);
    assert.ok(!start.done);
  });

  it("types at speaking pace, not spread over the whole line's time", () => {
    const early = typedAt(pages, 1, 12);
    assert.ok(early.shown > 5 && early.shown < total);
  });

  it("finishes with time to spare and then stops speaking", () => {
    const late = typedAt(pages, 12 * 0.9, 12);
    assert.equal(late.shown, total);
    assert.ok(late.done);
    assert.ok(!late.speaking);
  });

  it("only ever moves forward as time passes", () => {
    const long = paginate(LONG, 200);
    let page = 0;
    let shown = 0;
    for (let t = 0; t <= 14; t += 0.1) {
      const now = typedAt(long, t, 14);
      assert.ok(now.page >= page, "went back a page");
      if (now.page === page) assert.ok(now.shown >= shown, "lost characters");
      page = now.page;
      shown = now.shown;
    }
  });

  it("holds a full page before turning to the next, and is done by the end of the line", () => {
    const long = paginate(LONG, 200);
    const held = Array.from({ length: 140 }, (_, i) => typedAt(long, i / 10, 14)).filter((now) => !now.speaking && !now.done);
    assert.ok(held.length > 0, "never paused between pages");
    assert.ok(held.every((now) => now.page < long.length - 1));
    assert.ok(typedAt(long, 14, 14).done);
  });

  it("copes with no pages", () => {
    const empty = typedAt([], 3, 5);
    assert.deepEqual(empty.lines, []);
    assert.ok(empty.done);
  });
});
