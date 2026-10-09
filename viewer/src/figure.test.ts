import assert from "node:assert/strict";
import { test } from "node:test";
import { gaitFor, shade } from "./figure.ts";

test("a player's gait follows his speed: standing, walking, jogging, running, sprinting", () => {
  assert.equal(gaitFor(0).pose, "stand");
  assert.ok(gaitFor(1).amp < gaitFor(3).amp);
  assert.ok(gaitFor(3).amp < gaitFor(5).amp);
  assert.equal(gaitFor(8).pose, "lean");
  assert.ok(gaitFor(1).period > gaitFor(5).period, "a walk takes longer per stride than a run");
});

test("shade darkens toward black below 1 and lightens toward white above 1", () => {
  assert.equal(shade("#808080", 0.5), "#404040");
  assert.equal(shade("#000000", 1.5), "#808080");
  assert.equal(shade("#336699", 1), "#336699");
});
