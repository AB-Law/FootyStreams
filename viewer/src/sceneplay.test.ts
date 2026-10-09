import assert from "node:assert/strict";
import { test } from "node:test";
import type { AnyEvent } from "./events.ts";
import { sampleAt } from "./interpolate.ts";
import type { ReplayMeta } from "./meta.ts";
import { ScenePlayer, type SceneFrame } from "./sceneplay.ts";
import { MatchStore } from "./store.ts";

const clock = { period: 1, minute: 0, second: 0, stoppage: 0 };
const ctx = { score_home: 0, score_away: 0, attack_dir: 1 };
const L = 105;
const W = 68;
const RUN_MPS = 5;
const look = { skin_tone: 3, hair_style: "short", hair_colour: "black", facial_hair: "none", build: "lean" };

function team(name: string, ids: string[]): ReplayMeta["home"] {
  const kit = { pattern: "solid" as const, colours: ["#aa0000", "#ffffff"] };
  return {
    name,
    short_code: name.slice(0, 3).toUpperCase(),
    kits: { home: kit, away: kit },
    players: Object.fromEntries(ids.map((id) => [id, { name: `Player ${id}`, number: 7, appearance: look }])),
  };
}

function metaOf(home: string[], away: string[]): ReplayMeta {
  return { match_id: "test", home: team("Home", home), away: team("Away", away) };
}

interface Spot {
  id: string;
  /** Metres from the start of the pitch along it, and across it. */
  x: number;
  y: number;
  vx: number;
}

function frame(spots: Spot[], carrier: string | null, ball: { x: number; y: number }): AnyEvent {
  return {
    type: "frame",
    team: "none",
    clock,
    ctx,
    participants: [],
    pos: null,
    ball_pos_x: ball.x / L,
    ball_pos_y: ball.y / W,
    carrier_id: carrier,
    players: spots.map((spot) => ({ player_id: spot.id, x: spot.x / L, y: spot.y / W, speed_mps: Math.abs(spot.vx), vx: spot.vx, vy: 0, exhaustion: 0 })),
  } as AnyEvent;
}

/**
 * A carrier `a` running along the pitch at 5 m/s and a defender `d` held `gap(t)` metres ahead of him
 * (negative: behind) and `across` metres to one side, for `seconds` seconds, with the log's event
 * arriving after frame `at` and the ball changing hands one frame later.
 */
function duel(options: { gap: (t: number) => number; across: number; event: AnyEvent; at: number; seconds?: number }): { store: MatchStore; meta: ReplayMeta } {
  const store = new MatchStore();
  const seconds = options.seconds ?? 14;
  for (let t = 0; t <= seconds; t++) {
    const a = { id: "a", x: 30 + RUN_MPS * t, y: 30, vx: RUN_MPS };
    const d = { id: "d", x: a.x + options.gap(t), y: 30 + options.across, vx: RUN_MPS };
    const holder = t <= options.at ? "a" : "d";
    store.onEvent(frame([a, d], holder, holder === "a" ? { x: a.x + 0.9, y: 30 } : { x: d.x, y: d.y }));
    if (t === options.at) store.onEvent(options.event);
  }
  return { store, meta: metaOf(["a"], ["d"]) };
}

const tackled = { type: "dribble", team: "home", clock, ctx, participants: [], pos: null, player_id: "a", outcome: "tackled" } as AnyEvent;
const missedTackle = { type: "tackle", team: "away", clock, ctx, participants: [], pos: null, player_id: "d", target_id: "a", outcome: "missed" } as AnyEvent;

interface Seen {
  t: number;
  frame: SceneFrame;
  a: { x: number; y: number };
  d: { x: number; y: number };
}

/** Everything the scene player puts on the pitch, every 0.05 s, as world positions in metres. */
function watch(store: MatchStore, meta: ReplayMeta, from = 0, to = 12): Seen[] {
  const player = new ScenePlayer(store, meta);
  const out: Seen[] = [];
  for (let t = from; t <= to; t += 0.05) {
    const sample = sampleAt(store.frames, t);
    if (sample === null) continue;
    const frame = player.at(t, sample);
    const place = (id: string): { x: number; y: number } => {
      const real = sample.players.find((p) => p.id === id);
      const pose = frame.poses.get(id);
      return { x: (real?.x ?? 0) * L + (pose?.dxM ?? 0), y: (real?.y ?? 0) * W + (pose?.dyM ?? 0) };
    };
    out.push({ t, frame, a: place("a"), d: place("d") });
  }
  return out;
}

const during = (seen: Seen[]): Seen[] => seen.filter((moment) => moment.frame.poses.has("a"));

test("a tackled take-on is played on the real players: the carrier faces the way he runs and the tackler comes at him", () => {
  const { store, meta } = duel({ gap: () => 5, across: 1, event: tackled, at: 4 });
  const scene = during(watch(store, meta));
  assert.ok(scene.length > 20, "there is a scene");
  for (const moment of scene) {
    const pose = moment.frame.poses.get("a");
    if (pose?.lying === null) assert.equal(pose.facing, 1, `the carrier runs toward x = 1 but faces ${pose.facing} at ${moment.t.toFixed(2)}`);
  }
  const tackler = scene.map((moment) => moment.frame.poses.get("d")?.facing);
  assert.ok(tackler.some((facing) => facing === -1), "the tackler faces the carrier as he comes in");
  const closest = Math.min(...scene.map((moment) => Math.hypot(moment.a.x - moment.d.x, moment.a.y - moment.d.y)));
  assert.ok(closest < 1.3 && closest >= 0.78, `they come together at ${closest.toFixed(2)} m, no closer than a body`);
});

test("a scene starts and ends on the replay: nobody is out of place before it or after it", () => {
  const { store, meta } = duel({ gap: () => 5, across: 1, event: tackled, at: 4 });
  const seen = watch(store, meta);
  const scene = during(seen);
  const first = scene[0] as Seen;
  const last = scene.at(-1) as Seen;
  assert.ok(first.t > 0 && last.t < 12, "the scene sits inside the match");
  for (const edge of [first, last]) {
    const pose = edge.frame.poses.get("a");
    assert.ok(Math.hypot(pose?.dxM ?? 0, pose?.dyM ?? 0) < 0.15, `the carrier is on his replay place at ${edge.t.toFixed(2)}`);
    assert.ok((pose?.h ?? 0) < 0.05, "and on the ground");
  }
  assert.equal(seen.find((moment) => moment.t > last.t + 0.2)?.frame.poses.size, 0, "then there is no pose left");
  assert.equal(seen.every((moment) => moment.frame.poses.size === 0 || moment.frame.ball !== undefined), true);
});

test("a tackler who is far from the carrier is not brought in: the scene is left out", () => {
  const { store, meta } = duel({ gap: () => 16, across: 3, event: missedTackle, at: 4 });
  assert.equal(during(watch(store, meta)).length, 0, "no scene is played with nobody near");
});

test("a defender behind the carrier chases him from behind, and never runs through him", () => {
  const { store, meta } = duel({ gap: () => -4, across: 1.2, event: tackled, at: 4 });
  const scene = during(watch(store, meta));
  assert.ok(scene.length > 20, "there is a scene");
  for (const moment of scene) {
    assert.ok(moment.d.x - moment.a.x < 1.3, `the chaser is ${(moment.d.x - moment.a.x).toFixed(2)} m ahead of the carrier at ${moment.t.toFixed(2)}`);
    assert.ok(Math.hypot(moment.a.x - moment.d.x, moment.a.y - moment.d.y) >= 0.78, `they are on top of each other at ${moment.t.toFixed(2)}`);
  }
  const faces = scene.map((moment) => moment.frame.poses.get("d")?.facing);
  assert.ok(faces.some((facing) => facing === 1), "he faces the way the carrier runs");
});

test("nobody dashes: no one in a scene moves faster than a sprint in a single step, from the front or from behind", () => {
  for (const gap of [5, -4]) {
    const { store, meta } = duel({ gap: () => gap, across: 1, event: tackled, at: 4 });
    const seen = during(watch(store, meta));
    seen.slice(1).forEach((now, index) => {
      const before = seen[index] as Seen;
      if (now.t - before.t > 0.06) return;
      const dt = now.t - before.t;
      for (const who of ["a", "d"] as const) {
        const speed = Math.hypot(now[who].x - before[who].x, now[who].y - before[who].y) / dt;
        assert.ok(speed < 16, `${who} moves at ${speed.toFixed(1)} m/s at ${now.t.toFixed(2)} (gap ${gap})`);
      }
    });
  }
});

test("the ball stays with the players in a scene, and goes back to the replay as it ends", () => {
  const { store, meta } = duel({ gap: () => 5, across: 1, event: tackled, at: 4 });
  const seen = watch(store, meta);
  const withBall = seen.filter((moment) => moment.frame.ball !== null);
  assert.ok(withBall.length > 10, "the scene plays the ball");
  for (const moment of withBall) {
    const ball = { x: (moment.frame.ball?.x ?? 0) * L, y: (moment.frame.ball?.y ?? 0) * W };
    const nearest = Math.min(Math.hypot(ball.x - moment.a.x, ball.y - moment.a.y), Math.hypot(ball.x - moment.d.x, ball.y - moment.d.y));
    assert.ok(nearest < 3, `the ball is ${nearest.toFixed(2)} m from both players at ${moment.t.toFixed(2)}`);
  }
  const last = withBall.at(-1) as Seen;
  const after = seen.find((moment) => moment.t > last.t + 0.1) as Seen;
  assert.equal(after.frame.ball, null, "after the scene the ball is the replay's own");
});

test("a free kick is played with the taker running up and a wall of the opponents standing in front of him", () => {
  const store = new MatchStore();
  const taker = { id: "a", x: 50, y: 34, vx: 0 };
  const wall = ["w1", "w2", "w3"].map((id, index) => ({ id, x: 59, y: 33 + index, vx: 0 }));
  for (let t = 0; t <= 12; t++) {
    store.onEvent(frame([taker, ...wall], "a", { x: t < 9 ? 50 : 50 + (t - 8) * 8, y: 34 }));
    if (t === 1) store.onEvent({ type: "free_kick", team: "home", clock, ctx, participants: [], pos: null, taker_id: "a" } as AnyEvent);
  }
  const meta = metaOf(["a"], ["w1", "w2", "w3"]);
  const player = new ScenePlayer(store, meta);
  const sample = sampleAt(store.frames, 8.5);
  const frameAt = player.at(8.5, sample);
  assert.ok(frameAt.poses.has("a"), "the taker is in a scene");
  for (const id of ["w1", "w2", "w3"]) {
    const pose = frameAt.poses.get(id);
    assert.ok(pose !== undefined, `${id} stands in the wall`);
    assert.equal(pose?.facing, -1, `${id} faces the taker`);
  }
});
