import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { entryAfter, howLong, onAir, parseIndex, pastEntries, queuedSeconds, segmentScript, upcoming, type ChannelIndex } from "./channel.ts";

const entry = (id: string, airAt: number, duration: number) => ({
  id,
  file: `${id}.json`,
  kind: "banter",
  title: `Title ${id}`,
  headline: `Headline ${id}`,
  label: "Desk chat",
  guest: "",
  air_at: airAt,
  duration_s: duration,
});

const INDEX: ChannelIndex = {
  channel: "VPL News",
  generated_at: 0,
  cast: [],
  segments: [entry("a", 100, 60), entry("b", 160, 40), entry("c", 300, 30)],
};

describe("what is on air", () => {
  it("is the segment the clock is inside, with how far in and what follows", () => {
    const live = onAir(INDEX, 175);
    assert.equal(live.state, "live");
    if (live.state === "live") {
      assert.equal(live.entry.id, "b");
      assert.equal(live.t, 15);
      assert.equal(live.next?.id, "c");
    }
  });

  it("changes over on the second a segment ends", () => {
    const live = onAir(INDEX, 160);
    assert.equal(live.state === "live" && live.entry.id, "b");
  });

  it("is stand by in a gap, with the next segment named", () => {
    const gap = onAir(INDEX, 250);
    assert.equal(gap.state, "standby");
    assert.equal(gap.state === "standby" && gap.next?.id, "c");
  });

  it("is stand by before the first and after the last", () => {
    assert.equal(onAir(INDEX, 10).state, "standby");
    const after = onAir(INDEX, 9999);
    assert.equal(after.state === "standby" && after.next, null);
  });

  it("lists what is coming and how much airtime is queued", () => {
    assert.deepEqual(upcoming(INDEX, 120, 5).map((e) => e.id), ["b", "c"]);
    assert.deepEqual(upcoming(INDEX, 120, 1).map((e) => e.id), ["b"]);
    assert.equal(queuedSeconds(INDEX, 200), 130);
    assert.equal(queuedSeconds(INDEX, 9999), 0);
  });
});

describe("going back", () => {
  it("lists what has finished airing, most recent first, and never the one on air", () => {
    assert.deepEqual(pastEntries(INDEX, 175).map((e) => e.id), ["a"]);
    assert.deepEqual(pastEntries(INDEX, 250).map((e) => e.id), ["b", "a"]);
    assert.deepEqual(pastEntries(INDEX, 9999).map((e) => e.id), ["c", "b", "a"]);
    assert.deepEqual(pastEntries(INDEX, 50), []);
  });

  it("knows which segment follows another, so a replay can carry on through what aired", () => {
    const first = INDEX.segments[0]!;
    assert.equal(entryAfter(INDEX, first)?.id, "b");
    assert.equal(entryAfter(INDEX, INDEX.segments[2]!), null);
    assert.equal(entryAfter(INDEX, entry("zzz", 0, 1)), null);
  });
});

describe("reading the feed", () => {
  it("keeps good rows in air order and drops the rest", () => {
    const parsed = parseIndex({
      segments: [entry("late", 500, 10), { id: "broken" }, entry("early", 5, 10), { ...entry("zero", 9, 0) }],
      cast: [{ id: "med_a", name: "Ann" }, { nope: 1 }],
    });
    assert.deepEqual(parsed?.segments.map((e) => e.id), ["early", "late"]);
    assert.deepEqual(parsed?.cast, [{ id: "med_a", name: "Ann" }]);
  });

  it("falls back to the title when a row has no headline", () => {
    const row: Record<string, unknown> = { ...entry("a", 1, 5) };
    delete row.headline;
    delete row.guest;
    const parsed = parseIndex({ segments: [row] });
    assert.equal(parsed?.segments[0]?.headline, "Title a");
    assert.equal(parsed?.segments[0]?.guest, "");
  });

  it("is null for anything that is not a feed", () => {
    for (const junk of [null, 5, "x", [], {}, { segments: "no" }]) assert.equal(parseIndex(junk), null);
  });

  it("turns a segment file into a script the studio can play", () => {
    const script = segmentScript({
      id: "seg_1",
      kind: "interview",
      title: "A title",
      label: "Match report",
      screen: { kind: "score", title: "FULL TIME", rows: [{ label: "A", value: "2" }, { label: "B", value: "1" }] },
      guest: { id: "plr_1", name: "Khushe", kind: "player", role: "Player of the match", appearance: { skin_tone: 3 }, kit_primary: "#c8102e", kit_secondary: "#ffffff" },
      alert: "",
      ticker: ["one", 2, "three"],
      memories: [{ host: "Ann", kind: "running_joke", text: "the car park" }, { text: 5 }],
      lines: [
        { speaker_id: "a", speaker_name: "Ann", text: "Hello there", duration_ms: 3000 },
        { speaker_id: "b", text: 7 },
      ],
    });
    assert.equal(script?.lines.length, 1);
    assert.equal(script?.label, "Match report");
    assert.equal(script?.kind, "interview");
    assert.equal(script?.screen?.kind, "score");
    assert.equal(script?.guest?.name, "Khushe");
    assert.equal(script?.alert, undefined);
    assert.deepEqual(script?.ticker, ["one", "three"]);
    assert.equal(script?.memories?.length, 1);
  });

  it("plays a break: no lines, a few slides", () => {
    const script = segmentScript({
      id: "seg_2",
      kind: "break",
      title: "VPL News will be right back",
      lines: [],
      slides: [
        { kind: "ad", title: "Grafters Pies", lines: ["Proper pies"], rows: [], accent: "#d9822b", dark: "#4a250a", seconds: 6 },
        { kind: "table", title: "The table", lines: [], rows: [{ label: "A", value: "9 pts" }, { nope: 1 }], seconds: 7 },
        { kind: "ad", title: "Zero seconds", seconds: 0 },
        "junk",
      ],
    });
    assert.equal(script?.lines.length, 0);
    assert.equal(script?.slides?.length, 2);
    assert.equal(script?.slides?.[1]?.rows.length, 1);
    assert.equal(script?.slides?.[1]?.accent, "#f2c200");
  });

  it("refuses a segment with nothing to say or show", () => {
    assert.equal(segmentScript({ lines: [] }), null);
    assert.equal(segmentScript({ lines: [{ text: 1 }] }), null);
    assert.equal(segmentScript("no"), null);
  });

  it("says how long in words", () => {
    assert.equal(howLong(45), "45 s");
    assert.equal(howLong(600), "10 min");
  });
});
