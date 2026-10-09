import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { Slide } from "./commentary.ts";
import { drawSlides, fitScale, slideAt, slidesDuration } from "./slides.ts";

const slide = (kind: Slide["kind"], seconds: number, extra: Partial<Slide> = {}): Slide => ({
  kind,
  title: kind === "ad" ? "Mid-Table Mattresses" : "The table",
  lines: kind === "ad" ? ["Sleep through the relegation fight"] : kind === "fixture" ? ["Seisund County", "v", "Gathiski Albion", "Matchday 3"] : ["A very long headline about something that has just happened at a club"],
  rows: kind === "table" ? [{ label: "Seisund County", value: "9 pts" }, { label: "Bukach Harriers", value: "7 pts" }] : [],
  accent: "#d9822b",
  dark: "#4a250a",
  seconds,
  ...extra,
});

const SHOW = [slide("ad", 6), slide("table", 7), slide("results", 7, { lines: ["A 2-1 B", "C 0-0 D"] }), slide("fixture", 6), slide("breaking", 9)];

const rects: number[][] = [];
const fake = {
  fillStyle: "",
  globalAlpha: 1,
  fillRect: (x: number, y: number, w: number, h: number) => void rects.push([x, y, w, h]),
};
const ctx = fake as unknown as CanvasRenderingContext2D;

describe("break slides", () => {
  it("add up to the length of the break", () => {
    assert.equal(slidesDuration(SHOW), 35);
    assert.equal(slidesDuration([]), 0);
  });

  it("say which card is up and how far into it", () => {
    assert.deepEqual(slideAt(SHOW, 0), { index: 0, local: 0 });
    assert.deepEqual(slideAt(SHOW, 7), { index: 1, local: 1 });
    assert.deepEqual(slideAt(SHOW, 13), { index: 2, local: 0 });
    assert.deepEqual(slideAt(SHOW, 999), { index: 4, local: 9 });
    assert.deepEqual(slideAt([], 3), { index: 0, local: 0 });
  });

  it("scale text to the room there is", () => {
    assert.equal(fitScale("AB", 400), 4);
    assert.equal(fitScale("MID-TABLE MATTRESSES", 150), 1);
    assert.ok(fitScale("MID-TABLE MATTRESSES", 400) >= 2);
  });

  it("draw every kind of card, at every moment, on whole pixels and inside the picture", () => {
    for (let t = 0; t <= slidesDuration(SHOW) + 2; t += 0.37) {
      rects.length = 0;
      drawSlides(ctx, SHOW, t, t * 1.3);
      assert.ok(rects.length > 20, `nothing drawn at ${t}`);
      for (const rect of rects) assert.ok(rect.every(Number.isInteger), `off the pixel grid at ${t}: ${rect}`);
      const stray = rects.filter(([x, y, w, h]) => (x ?? 0) < -1 || (y ?? 0) < 0 || (x ?? 0) + (w ?? 0) > 481 || (y ?? 0) + (h ?? 0) > 271);
      assert.deepEqual(stray, [], `drawn outside the picture at ${t}`);
    }
  });

  it("draw nothing but the backdrop when there are no cards", () => {
    rects.length = 0;
    drawSlides(ctx, [], 1, 1);
    assert.equal(rects.length, 1);
  });

  it("flash the breaking card between two reds", () => {
    const colours = new Set<string>();
    const recording = {
      globalAlpha: 1,
      fillStyle: "",
      fillRect() {
        colours.add(String(this.fillStyle));
      },
    };
    for (const clock of [0, 0.4]) drawSlides(recording as unknown as CanvasRenderingContext2D, [slide("breaking", 9)], 3, clock);
    assert.ok(colours.has("#c8102e"));
    assert.ok(colours.has("#7a0c1c"));
  });
});
