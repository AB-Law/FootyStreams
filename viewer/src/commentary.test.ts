import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { cueAt, lineAt, lineStarts, parseResult, scriptDuration, speakersOf, type CommentaryScript } from "./commentary.ts";

const SCRIPT: CommentaryScript = {
  match_id: "mch_test",
  lines: [
    { speaker_id: "a", speaker_name: "Ann", text: "Hello", beat: "intro", duration_ms: 2000 },
    { speaker_id: "b", speaker_name: "Bob", text: "Colour", beat: "club_colour", duration_ms: 3000 },
  ],
};

describe("commentary timing", () => {
  it("builds cumulative starts and total duration", () => {
    assert.deepEqual(lineStarts(SCRIPT), [0, 2, 5]);
    assert.equal(scriptDuration(SCRIPT), 5);
  });

  it("picks the active line by time", () => {
    assert.equal(lineAt(SCRIPT, 0)?.speaker_name, "Ann");
    assert.equal(lineAt(SCRIPT, 1.9)?.speaker_name, "Ann");
    assert.equal(lineAt(SCRIPT, 2)?.speaker_name, "Bob");
    assert.equal(lineAt(SCRIPT, 99)?.speaker_name, "Bob");
  });
});

describe("cues", () => {
  it("says where the current line began and how far into it we are", () => {
    const cue = cueAt(SCRIPT, 3);
    assert.equal(cue?.index, 1);
    assert.equal(cue?.start, 2);
    assert.equal(cue?.duration, 3);
    assert.equal(cue?.elapsed, 1);
  });

  it("holds on the last line once the script is over", () => {
    const cue = cueAt(SCRIPT, 99);
    assert.equal(cue?.index, 1);
    assert.equal(cue?.elapsed, 3);
  });

  it("has no cue for an empty script", () => {
    assert.equal(cueAt({ match_id: "m", lines: [] }, 0), null);
  });
});

describe("speakers", () => {
  it("lists each speaker once, in the order they first speak", () => {
    const again: CommentaryScript = { match_id: "m", lines: [...SCRIPT.lines, { ...SCRIPT.lines[0]!, text: "Again" }] };
    assert.deepEqual(speakersOf(again), [
      { id: "a", name: "Ann" },
      { id: "b", name: "Bob" },
    ]);
  });
});

describe("parseResult", () => {
  const intro = (text: string): CommentaryScript => ({ match_id: "m", lines: [{ speaker_id: "a", speaker_name: "Ann", text, beat: "intro", duration_ms: 5000 }] });

  it("reads the score out of the intro line", () => {
    const result = parseResult(intro("Good evening from the VPL News desk. Full time: Seisund County 2, Bukach Harriers 1. Let's walk through it."));
    assert.deepEqual(result, { home: "Seisund County", homeGoals: 2, away: "Bukach Harriers", awayGoals: 1 });
  });

  it("copes with accented club names", () => {
    const result = parseResult(intro("Full time: Gathiški Town 0, Ælfwick Rovers 3."));
    assert.equal(result?.home, "Gathiški Town");
    assert.equal(result?.away, "Ælfwick Rovers");
    assert.equal(result?.awayGoals, 3);
  });

  it("is null when the intro states no score", () => {
    assert.equal(parseResult(intro("Good evening and welcome.")), null);
  });
});
