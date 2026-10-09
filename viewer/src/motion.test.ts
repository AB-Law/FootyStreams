import assert from "node:assert/strict";
import { test } from "node:test";
import type { AnyEvent } from "./events.ts";
import { sampleAt } from "./interpolate.ts";
import { MatchStore } from "./store.ts";

const clock = { period: 1, minute: 0, second: 0, stoppage: 0 };

interface Mover {
  x: number;
  y: number;
  vx?: number;
  vy?: number;
}

function frame(runner: Mover, extra: { carrier?: string | null; ballX?: number; ballHeight?: number } = {}): AnyEvent {
  return {
    type: "frame",
    team: "none",
    clock,
    ctx: { score_home: 0, score_away: 0, attack_dir: 1 },
    participants: [],
    pos: null,
    ball_pos_x: extra.ballX ?? 0.5,
    ball_pos_y: 0.5,
    carrier_id: extra.carrier ?? null,
    ...(extra.ballHeight === undefined ? {} : { ball_height_m: extra.ballHeight }),
    players: [{ player_id: "a", speed_mps: 5, exhaustion: 0, ...runner }],
  } as AnyEvent;
}

function loaded(...events: AnyEvent[]): MatchStore {
  const store = new MatchStore();
  events.forEach((event) => store.onEvent(event));
  return store;
}

test("a run with velocities curves through its frames instead of cutting the corner", () => {
  // Running straight along the pitch, then turning to run across it: the path bends smoothly.
  const store = loaded(
    frame({ x: 0.4, y: 0.5, vx: 8, vy: 0 }),
    frame({ x: 0.476, y: 0.5, vx: 8, vy: 0 }),
    frame({ x: 0.476, y: 0.6, vx: 0, vy: 8 }),
  );
  const straight = sampleAt(store.frames, 1)?.players[0];
  const bend = sampleAt(store.frames, 1.5)?.players[0];
  assert.ok(Math.abs((straight?.x ?? 0) - 0.476) < 1e-9);
  assert.ok(bend !== undefined && bend.x > 0.476 - 1e-9, "the turn is rounded, not cut");
  assert.ok(bend !== undefined && bend.y > 0.5 && bend.y < 0.6);
});

test("smoothing never strays far from the two frames it joins", () => {
  const store = loaded(frame({ x: 0.4, y: 0.5, vx: 30, vy: 0 }), frame({ x: 0.41, y: 0.5, vx: -30, vy: 0 }));
  for (let step = 0; step <= 10; step++) {
    const x = sampleAt(store.frames, step / 10)?.players[0]?.x ?? 0;
    assert.ok(x >= 0.4 - 0.016 && x <= 0.41 + 0.016, `x ${x} at ${step / 10}`);
  }
});

test("without velocities the path is the straight line it always was", () => {
  const store = loaded(frame({ x: 0.4, y: 0.5 }), frame({ x: 0.5, y: 0.5 }));
  assert.ok(Math.abs((sampleAt(store.frames, 0.5)?.players[0]?.x ?? 0) - 0.45) < 1e-9);
});

test("a running carrier plays the ball ahead of him and a standing one keeps it at his feet", () => {
  const running = loaded(frame({ x: 0.5, y: 0.5, vx: 6, vy: 0 }, { carrier: "a" }), frame({ x: 0.55, y: 0.5, vx: 6, vy: 0 }, { carrier: "a" }));
  const ahead = sampleAt(running.frames, 0)?.ballX ?? 0;
  assert.ok(ahead > 0.5 + 0.5 / 105, `ball ${ahead}`);
  const standing = loaded(frame({ x: 0.5, y: 0.5, vx: 0, vy: 0 }, { carrier: "a" }), frame({ x: 0.5, y: 0.5, vx: 0, vy: 0 }, { carrier: "a" }));
  assert.equal(sampleAt(standing.frames, 0)?.ballX, 0.5);
});

test("the ball's height comes from the frames when they carry it", () => {
  const store = loaded(frame({ x: 0.5, y: 0.5 }, { ballHeight: 0 }), frame({ x: 0.5, y: 0.5 }, { ballHeight: 4 }));
  const mid = sampleAt(store.frames, 0.5)?.ballHeight ?? 0;
  assert.ok(mid > 4 && mid < 7, `height ${mid}`);
});
