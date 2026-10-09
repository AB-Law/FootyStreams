import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { CommentaryLine, CommentaryScript } from "./commentary.ts";
import { firstSentence, tickerItems } from "./ticker.ts";

const line = (beat: CommentaryLine["beat"], text: string): CommentaryLine => ({ speaker_id: "a", speaker_name: "Ann", text, beat, duration_ms: 5000 });

describe("firstSentence", () => {
  it("takes the first sentence", () => {
    assert.equal(firstSentence("One goal. Then another one."), "One goal.");
  });

  it("cuts a long sentence at a word and adds an ellipsis", () => {
    const cut = firstSentence("alpha beta gamma delta epsilon zeta", 20);
    assert.ok(cut.length <= 20);
    assert.ok(cut.endsWith("…"));
    assert.ok(!cut.includes("zeta"));
  });
});

describe("tickerItems", () => {
  const script: CommentaryScript = {
    match_id: "m",
    lines: [line("intro", "Welcome. Full time: A 2, B 1."), line("club_colour", "A were founded in 1871. More."), line("club_colour", "A were founded in 1871. More."), line("wrap", "Shots 12-14.")],
  };

  it("leads with the result and skips the intro and repeats", () => {
    const items = tickerItems(script, { home: "A", homeGoals: 2, away: "B", awayGoals: 1 });
    assert.deepEqual(items, ["A 2-1 B", "A were founded in 1871.", "Shots 12-14."]);
  });

  it("falls back to the channel name for an empty script", () => {
    assert.deepEqual(tickerItems({ match_id: "m", lines: [] }, null), ["VPL News desk"]);
  });
});
