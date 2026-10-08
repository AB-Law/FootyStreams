import assert from "node:assert/strict";
import { test } from "node:test";

import { normalise, textWidth } from "./font.ts";
import type { KitMeta, ReplayMeta, TeamMeta } from "./meta.ts";
import { pickKits, shirtColour } from "./palette.ts";

function team(home: string, away: string): TeamMeta {
  const kit = (colour: string): KitMeta => ({ pattern: "solid", colours: [colour, "#ffffff"] });
  return { name: "T", short_code: "TTT", kits: { home: kit(home), away: kit(away) }, players: {} };
}

function replay(homeKit: string, awayKit: string, awayAlt: string): ReplayMeta {
  return { match_id: "m", home: team(homeKit, "#000000"), away: team(awayKit, awayAlt) };
}

test("pickKits keeps the away side in its home kit when the colours differ", () => {
  const kits = pickKits(replay("#c8102e", "#0b3d91", "#ffffff"));
  assert.equal(kits.away.primary, "#0b3d91");
});

test("pickKits switches the away side to its away kit on a clash", () => {
  const kits = pickKits(replay("#c8102e", "#c81030", "#ffffff"));
  assert.equal(kits.away.primary, "#ffffff");
});

test("shirtColour follows the pattern", () => {
  const kit = { pattern: "stripes" as const, primary: "#111111", secondary: "#eeeeee" };
  assert.equal(shirtColour(kit, 0, 0), "#111111");
  assert.equal(shirtColour(kit, 1, 0), "#eeeeee");
  assert.equal(shirtColour({ ...kit, pattern: "hoops" }, 0, 1), "#eeeeee");
  assert.equal(shirtColour({ ...kit, pattern: "halves" }, 4, 0), "#eeeeee");
});

test("normalise strips accents and replaces glyphs the font lacks", () => {
  assert.equal(normalise("Gathiški Ælf"), "GATHISKI ?LF");
});

test("textWidth counts three pixels per glyph plus one between", () => {
  assert.equal(textWidth("AB"), 7);
  assert.equal(textWidth("AB", 2), 14);
});
