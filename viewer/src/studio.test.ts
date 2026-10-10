import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { scriptDuration, speakersOf, type CommentaryScript } from "./commentary.ts";
import { Studio } from "./studio.ts";
import { STUDIO_H, STUDIO_W } from "./studio-set.ts";

// A canvas that only remembers where things were drawn, so the whole studio can be driven in node.
const rects: number[][] = [];
const images: number[][] = [];
const fake = {
  fillStyle: "",
  globalAlpha: 1,
  imageSmoothingEnabled: true,
  fillRect: (x: number, y: number, w: number, h: number) => void rects.push([x, y, w, h]),
  drawImage: (_image: unknown, x: number, y: number) => void images.push([x, y]),
  save: () => undefined,
  restore: () => undefined,
  beginPath: () => undefined,
  rect: () => undefined,
  clip: () => undefined,
};
Object.assign(globalThis, { document: { createElement: () => ({ width: 0, height: 0, getContext: () => fake }) } });
const ctx = fake as unknown as CanvasRenderingContext2D;

const LONG = "The desk has a great deal to say about this one, starting with how the home side set up and ending with who was named player of the match. ".repeat(3).trim();

const SCRIPT: CommentaryScript = {
  match_id: "m",
  lines: [
    { speaker_id: "med_1", speaker_name: "Chille-Jaichàult", text: "Good evening from the VPL News desk. Full time: Seisund County 2, Bukach Harriers 1.", beat: "intro", duration_ms: 9000 },
    { speaker_id: "med_2", speaker_name: "Kitpet", text: LONG, beat: "club_colour", duration_ms: 14000 },
    { speaker_id: "med_4", speaker_name: "Yitsi", text: "Short.", beat: "player_focus", duration_ms: 3000 },
    { speaker_id: "med_1", speaker_name: "Chille-Jaichàult", text: "That is all from us.", beat: "wrap", duration_ms: 4000 },
  ],
};

function studioFor(script: CommentaryScript): Studio {
  const studio = new Studio(speakersOf(script));
  studio.setScript(script);
  return studio;
}

describe("studio", () => {
  const studio = studioFor(SCRIPT);

  it("draws every moment of the script without a stray half pixel or a bad number", () => {
    rects.length = 0;
    images.length = 0;
    for (let t = 0; t <= scriptDuration(SCRIPT) + 3; t += 0.37) studio.draw(ctx, t);
    assert.ok(rects.length > 1000);
    for (const rect of [...rects, ...images]) assert.ok(rect.every(Number.isInteger), `off the pixel grid: ${rect}`);
    for (const [, , w, h] of rects) assert.ok((w ?? 0) >= 0 && (h ?? 0) >= 0);
  });

  it("keeps what it draws on the screen, apart from the ticker, which the real canvas clips", () => {
    rects.length = 0;
    studio.draw(ctx, 20);
    const ticker = 250;
    const stray = rects.filter(([x, y, w, h]) => (y ?? 0) < ticker && ((x ?? 0) < 0 || (y ?? 0) < 0 || (x ?? 0) + (w ?? 0) > STUDIO_W || (y ?? 0) + (h ?? 0) > STUDIO_H));
    assert.deepEqual(stray, []);
  });

  it("seats each speaker once and gives them a stable colour", () => {
    assert.equal(studio.accentOf("med_1"), studio.accentOf("med_1"));
    assert.notEqual(studio.accentOf("med_1"), studio.accentOf("med_2"));
    assert.notEqual(studio.accentOf("med_2"), studio.accentOf("med_4"));
  });

  it("copes with a desk of one and with no script lines at all", () => {
    const solo = studioFor({ match_id: "m", lines: [{ ...SCRIPT.lines[0]!, speaker_id: "only" }] });
    solo.draw(ctx, 2);
    const nobody = studioFor({ match_id: "m", lines: [] });
    nobody.draw(ctx, 0);
  });
});
