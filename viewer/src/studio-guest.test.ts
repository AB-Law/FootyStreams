import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { guestLook } from "./anchor-look.ts";
import type { CommentaryScript, Guest } from "./commentary.ts";
import { Studio } from "./studio.ts";
import { bubbleLeft } from "./studio-hud.ts";
import { STUDIO_W } from "./studio-set.ts";

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

const HOSTS = [
  { id: "med_a", name: "Ann" },
  { id: "med_b", name: "Bob" },
  { id: "med_c", name: "Cy" },
];

const GUEST: Guest = {
  id: "plr_1",
  name: "Khushe",
  kind: "player",
  role: "Player of the match",
  appearance: { skin_tone: 5, hair_style: "curly", hair_colour: "black", facial_hair: "beard", build: "athletic" },
  kit_primary: "#c8102e",
  kit_secondary: "#ffffff",
};

const interview = (extra: Partial<CommentaryScript> = {}): CommentaryScript => ({
  match_id: "seg",
  label: "Interview",
  guest: GUEST,
  lines: [
    { speaker_id: "med_a", speaker_name: "Ann", text: "Welcome to the desk, Khushe. Tell us about the winner.", duration_ms: 5000 },
    { speaker_id: "plr_1", speaker_name: "Khushe", text: "It was a team goal, to be honest with you.", duration_ms: 5000 },
  ],
  ...extra,
});

function studioFor(script: CommentaryScript): Studio {
  const studio = new Studio(HOSTS);
  studio.setScript(script);
  return studio;
}

describe("a guest on the desk", () => {
  it("looks like themselves, in their club colours", () => {
    const look = guestLook(GUEST);
    assert.equal(look.appearance.hair_style, "curly");
    assert.equal(look.appearance.facial_hair, "beard");
    assert.equal(look.jacket, "#c8102e");
    assert.equal(look.accent, "#ffffff");
    assert.equal(look.tie, false);
  });

  it("copes with a guest the world gave few details for", () => {
    const look = guestLook({ ...GUEST, appearance: {} });
    assert.equal(look.appearance.hair_style, "short");
    assert.equal(look.appearance.skin_tone, 3);
  });

  it("sits in a fourth chair, and is drawn with the hosts", () => {
    const studio = studioFor(interview());
    images.length = 0;
    studio.draw(ctx, 6);
    const chairs = images.filter(([, y]) => (y ?? 0) >= 141 && (y ?? 0) <= 143).map(([x]) => x);
    assert.equal(chairs.length, 4);
    assert.ok(chairs.includes(440 - 32));
    assert.equal(studio.accentOf("plr_1"), "#c8102e");
  });

  it("goes when the next segment has no guest", () => {
    const studio = studioFor(interview());
    studio.setScript(interview({ guest: null }));
    images.length = 0;
    studio.draw(ctx, 6);
    assert.equal(images.filter(([, y]) => (y ?? 0) >= 141 && (y ?? 0) <= 143).length, 3);
  });

  it("draws the whole interview on whole pixels", () => {
    const studio = studioFor(interview());
    rects.length = 0;
    images.length = 0;
    for (let t = 0; t <= 12; t += 0.37) studio.draw(ctx, t, { clock: t * 1.1 });
    for (const rect of [...rects, ...images]) assert.ok(rect.every(Number.isInteger), `off the pixel grid: ${rect}`);
  });

  it("keeps the speech bubble on the screen with the tail on the guest", () => {
    for (const x of [90, 120, 240, 360, 440]) {
      const left = bubbleLeft(x);
      assert.ok(left >= 4 && left + 330 <= STUDIO_W - 4, `bubble off the screen for ${x}`);
      assert.ok(x >= left + 24 && x <= left + 330 - 24, `tail misses the speaker at ${x}`);
    }
    assert.equal(bubbleLeft(240), 75);
  });
});

describe("breaking news on the desk", () => {
  const breaking = (): CommentaryScript => ({
    match_id: "seg",
    kind: "breaking",
    label: "Breaking news",
    alert: "Seisund County sack their manager",
    lines: [{ speaker_id: "med_a", speaker_name: "Ann", text: "We are just getting this in, and we will bring you more.", duration_ms: 5000 }],
  });

  it("puts the banner up while they talk, in place of the lower third", () => {
    const studio = studioFor(breaking());
    rects.length = 0;
    studio.draw(ctx, 2, { clock: 0 });
    assert.ok(rects.some(([x, y, w, h]) => x === 7 && y === 214 && w === 466 && h === 15), "no banner");
  });

  it("scrolls a headline that is too long for the banner", () => {
    const long = { ...breaking(), alert: "A very long headline ".repeat(8).trim() };
    const studio = studioFor(long);
    for (const clock of [0, 1.7, 5.3]) {
      rects.length = 0;
      studio.draw(ctx, 2, { clock });
      for (const rect of rects) assert.ok(rect.every(Number.isInteger));
    }
  });

  it("is only the banner when something is said: no banner on a quiet desk", () => {
    const studio = studioFor({ ...breaking(), alert: "" });
    rects.length = 0;
    studio.draw(ctx, 2, { clock: 0 });
    assert.ok(!rects.some(([x, y, w, h]) => x === 7 && y === 214 && w === 466 && h === 15));
  });
});

describe("a break on the desk studio", () => {
  it("shows slides instead of the desk, with the ticker still running", () => {
    const studio = new Studio(HOSTS);
    studio.setScript({
      match_id: "seg",
      kind: "break",
      lines: [],
      slides: [{ kind: "ad", title: "Grafters Pies", lines: ["Proper pies"], rows: [], accent: "#d9822b", dark: "#4a250a", seconds: 6 }],
    });
    studio.setTicker(["FT A 2-1 B"]);
    images.length = 0;
    rects.length = 0;
    studio.draw(ctx, 3, { clock: 3 });
    assert.equal(images.length, 0, "anchors drawn during a break");
    assert.ok(rects.some(([, y]) => y === 250), "no ticker");
    for (const rect of rects) assert.ok(rect.every(Number.isInteger));
  });
});
