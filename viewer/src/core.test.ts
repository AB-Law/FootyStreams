import assert from "node:assert/strict";
import { test } from "node:test";

import type { AnyEvent } from "./events.ts";
import { deadSpans, isDead } from "./deadtime.ts";
import { sampleAt } from "./interpolate.ts";
import { overlaysAt } from "./overlays.ts";
import { Playback } from "./playback.ts";
import { refereeTrack } from "./referee.ts";
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

test("refereeTrack never moves faster than a person can run, even when the ball and an incident jump", () => {
  const events = Array.from({ length: 80 }, (_, second) => frame(second < 40 ? 0.1 : 0.9));
  const foul = { type: "foul", team: "home", pos: { x: 0.6, y: 0.2 }, clock, ctx: { score_home: 0, score_away: 0, attack_dir: 1 }, participants: [] } as AnyEvent;
  const store = loaded(...events.slice(0, 55), foul, ...events.slice(55));
  let previous = refereeTrack(store.frames, store.marks, 0)?.spot;
  for (let step = 1; step <= 790; step++) {
    const spot = refereeTrack(store.frames, store.marks, step / 10)?.spot;
    assert.ok(previous !== undefined && spot !== undefined);
    const metres = Math.hypot((spot.x - previous.x) * 105, (spot.y - previous.y) * 68);
    assert.ok(metres <= 0.65 + 1e-9, `jumped ${metres} m at ${step / 10}s`);
    previous = spot;
  }
});

test("refereeTrack reports the incident while he is at a foul", () => {
  const foul = { type: "foul", team: "home", pos: { x: 0.6, y: 0.2 }, clock, ctx: { score_home: 0, score_away: 0, attack_dir: 1 }, participants: [] } as AnyEvent;
  const store = loaded(...Array.from({ length: 30 }, () => frame(0.5)), foul, ...Array.from({ length: 30 }, () => frame(0.5)));
  assert.equal(refereeTrack(store.frames, store.marks, 31)?.incident, true);
  assert.equal(refereeTrack(store.frames, store.marks, 10)?.incident, false);
  assert.equal(refereeTrack(store.frames, store.marks, 50)?.incident, false);
});

function withCarrier(frameEvent: AnyEvent, carrier: string, positions: Record<string, number>): AnyEvent {
  const base = frameEvent as unknown as { players: { player_id: string; x: number }[] };
  base.players.forEach((player) => (player.x = positions[player.player_id] ?? player.x));
  return { ...(frameEvent as object), carrier_id: carrier } as AnyEvent;
}

test("the ball stays on its carrier, and a pass carries it from one player to the other", () => {
  const first = withCarrier(frame(0.2), "a", { a: 0.2, b: 0.4 });
  const second = withCarrier(frame(0.2), "b", { a: 0.2, b: 0.4 });
  const store = loaded(first, second, second);
  assert.equal(sampleAt(store.frames, 0)?.ballX, 0.2);
  assert.equal(sampleAt(store.frames, 0.05)?.ballX !== undefined && (sampleAt(store.frames, 0.05)?.ballX ?? 0) < 0.25, true);
  const landed = sampleAt(store.frames, 0.9);
  assert.ok(Math.abs((landed?.ballX ?? 0) - 0.4) < 1e-9);
  assert.equal(sampleAt(store.frames, 1.5)?.ballX, 0.4);
});

test("the ball never jumps between two samples a tenth of a second apart", () => {
  const first = withCarrier(frame(0.2), "a", { a: 0.2, b: 0.6 });
  const second = withCarrier(frame(0.2), "b", { a: 0.2, b: 0.6 });
  const store = loaded(first, second, second);
  let previous = sampleAt(store.frames, 0)?.ballX ?? 0;
  for (let step = 1; step <= 20; step++) {
    const ball = sampleAt(store.frames, step / 10)?.ballX ?? 0;
    assert.ok(Math.abs(ball - previous) * 105 <= 105 * 0.4 * 0.2, `jump at ${step / 10}`);
    previous = ball;
  }
});

test("deadSpans finds a long stoppage, keeps a lead-in and ignores short pauses", () => {
  const moving = (x: number): AnyEvent => frame(x);
  const events = [moving(0.1), moving(0.2), ...Array.from({ length: 10 }, () => moving(0.3)), moving(0.4), moving(0.41), moving(0.41), moving(0.5)];
  const store = loaded(...events);
  const spans = deadSpans(store.frames);
  assert.equal(spans.length, 1);
  assert.equal(spans[0]?.start, 3.5);
  assert.equal(isDead(spans, 5), true);
  assert.equal(isDead(spans, 2), false);
  assert.equal(isDead(spans, 13), false);
});
