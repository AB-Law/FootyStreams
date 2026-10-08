import assert from "node:assert/strict";
import { test } from "node:test";

import type { AnyEvent } from "./events.ts";
import { sampleAt } from "./interpolate.ts";
import { overlaysAt } from "./overlays.ts";
import { Playback } from "./playback.ts";
import { replayNdjson } from "./source.ts";
import { MatchStore } from "./store.ts";

const clock = { period: 1, minute: 0, second: 0, stoppage: 0 };

function frame(x: number, scoreHome = 0, ids = ["a", "b"]): AnyEvent {
  return {
    type: "frame",
    team: "none",
    clock,
    ctx: { score_home: scoreHome, score_away: 0, attack_dir: 1 },
    participants: [],
    ball_pos_x: x,
    ball_pos_y: 0.5,
    carrier_id: null,
    players: ids.map((id) => ({ player_id: id, x, y: 0.5, speed_mps: 3, exhaustion: 0 })),
  } as AnyEvent;
}

function loaded(...events: AnyEvent[]): MatchStore {
  const store = new MatchStore();
  events.forEach((event) => store.onEvent(event));
  return store;
}

test("sampleAt blends positions halfway between two frames", () => {
  const store = loaded(frame(0.2), frame(0.3));
  const sample = sampleAt(store.frames, 0.5);
  assert.ok(sample);
  assert.ok(Math.abs(sample.ballX - 0.25) < 1e-9);
  assert.ok(Math.abs((sample.players[0]?.x ?? 0) - 0.25) < 1e-9);
});

test("sampleAt holds the last frame past the end (no extrapolation)", () => {
  const store = loaded(frame(0.2), frame(0.3));
  assert.equal(sampleAt(store.frames, 5)?.ballX, 0.3);
});

test("sampleAt does not slide across a reset such as the half-time swap", () => {
  const store = loaded(frame(0.1), frame(0.9));
  const sample = sampleAt(store.frames, 0.5);
  assert.equal(sample?.ballX, 0.1);
  assert.equal(sample?.players[0]?.x, 0.1);
});

test("sampleAt holds a player who is absent from the next frame", () => {
  const store = loaded(frame(0.2, 0, ["a", "b"]), frame(0.25, 0, ["a", "c"]));
  const sample = sampleAt(store.frames, 0.5);
  assert.equal(sample?.players[1]?.id, "b");
  assert.equal(sample?.players[1]?.x, 0.2);
});

test("sampleAt is null with no frames", () => {
  assert.equal(sampleAt([], 0), null);
});

test("onEvent ignores unknown event types", () => {
  const store = loaded({ type: "review" }, { type: "something_new", payload: 1 } as AnyEvent, frame(0.2));
  assert.equal(store.frames.length, 1);
  assert.equal(store.marks.length, 0);
});

test("onEvent turns a goal into a mark stamped with the latest frame time", () => {
  const goal = { type: "goal", team: "home", clock: { ...clock, minute: 42 }, ctx: { score_home: 1, score_away: 0, attack_dir: 1 }, participants: [], scorer_id: "a", assist_id: null, own_goal: false } as AnyEvent;
  const store = loaded(frame(0.2), frame(0.3), goal);
  assert.deepEqual(store.marks, [{ kind: "goal", t: 1, team: "home", scorerId: "a", ownGoal: false, scoreHome: 1, scoreAway: 0, minute: 42 }]);
});

test("overlaysAt shows a mark inside its window and stretches it with speed", () => {
  const store = loaded(
    frame(0.2), frame(0.2),
    { type: "card", team: "home", clock, ctx: { score_home: 0, score_away: 0, attack_dir: 1 }, participants: [], player_id: "a", colour: "yellow" } as AnyEvent,
  );
  assert.equal(overlaysAt(store.marks, 1.5, 1).length, 1);
  assert.equal(overlaysAt(store.marks, 5, 1).length, 0);
  assert.equal(overlaysAt(store.marks, 5, 16).length, 1);
  assert.equal(overlaysAt(store.marks, 0.5, 1).length, 0);
});

test("Playback advances at speed, stops at the end and restarts from there", () => {
  const playback = new Playback();
  playback.toggle(100);
  playback.speed = 4;
  playback.advance(2, 100);
  assert.equal(playback.t, 8);
  playback.advance(100, 100);
  assert.equal(playback.t, 100);
  assert.equal(playback.playing, false);
  playback.toggle(100);
  assert.equal(playback.t, 0);
  assert.equal(playback.playing, true);
});

test("replayNdjson feeds every non-blank line and keeps order", () => {
  const seen: string[] = [];
  replayNdjson('{"type":"a"}\n\n{"type":"b"}\n', (event) => seen.push(event.type));
  assert.deepEqual(seen, ["a", "b"]);
});
