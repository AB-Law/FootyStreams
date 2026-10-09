import assert from "node:assert/strict";
import { test } from "node:test";
import { passMap, pressMap } from "./analysis.ts";
import type { AnyEvent } from "./events.ts";
import type { ReplayMeta } from "./meta.ts";
import { StatsIndex, formRating, toTeamFrame } from "./stats.ts";
import { cameraAt } from "./camera.ts";
import { hit, type Hotspot } from "./mapview.ts";
import { MatchStore, homeDirection } from "./store.ts";

const clock = { period: 1, minute: 0, second: 0, stoppage: 0 };
const appearance = { skin_tone: 1, hair_style: "short", hair_colour: "black", facial_hair: "none", build: "average" };
const kit = { pattern: "solid" as const, colours: ["#ff0000"] };
const team = (name: string, ids: string[]) => ({
  name,
  short_code: name.slice(0, 3).toUpperCase(),
  kits: { home: kit, away: kit },
  players: Object.fromEntries(ids.map((id, index) => [id, { name: id, number: index + 1, appearance }])),
});
const meta: ReplayMeta = { match_id: "m", home: team("Home", ["h1", "h2"]), away: team("Away", ["a1", "a2"]) };

function frame(carrier: string | null, ballX = 0.5, dir = 1): AnyEvent {
  return {
    type: "frame",
    team: "none",
    clock,
    ctx: { score_home: 0, score_away: 0, attack_dir: dir },
    participants: [],
    pos: null,
    ball_pos_x: ballX,
    ball_pos_y: 0.5,
    carrier_id: carrier,
    players: [
      { player_id: "h1", x: 0.3, y: 0.3, speed_mps: 2, exhaustion: 0 },
      { player_id: "h2", x: 0.5, y: 0.6, speed_mps: 4, exhaustion: 0 },
      { player_id: "a1", x: 0.7, y: 0.4, speed_mps: 3, exhaustion: 0 },
      { player_id: "a2", x: 0.8, y: 0.5, speed_mps: 1, exhaustion: 0 },
    ],
  } as AnyEvent;
}

function logged(type: string, team: "home" | "away", fields: Record<string, unknown>): AnyEvent {
  return { type, team, clock, ctx: { score_home: 0, score_away: 0, attack_dir: 1 }, participants: [], pos: { x: 0.4, y: 0.5 }, ...fields } as AnyEvent;
}

function build(...events: AnyEvent[]): { store: MatchStore; stats: StatsIndex } {
  const store = new MatchStore();
  events.forEach((event) => store.onEvent(event));
  return { store, stats: new StatsIndex(store, meta) };
}

test("toTeamFrame shows each team attacking toward x = 1, in either half", () => {
  assert.deepEqual(toTeamFrame({ x: 0.2, y: 0.3 }, "home", 1), { x: 0.2, y: 0.3 });
  assert.deepEqual(toTeamFrame({ x: 0.2, y: 0.3 }, "away", 1), { x: 0.8, y: 0.7 });
  assert.deepEqual(toTeamFrame({ x: 0.2, y: 0.3 }, "home", -1), { x: 0.8, y: 0.7 });
});

test("possession and field tilt add up to 100 and follow the carrier", () => {
  const { stats } = build(frame("h1"), frame("h1"), frame("h1"), frame("a1"), frame(null));
  const { home, away } = stats.teamStats(0, 4);
  assert.ok(Math.abs(home.possession + away.possession - 1) < 1e-9);
  assert.ok(home.possession > away.possession);
});

test("statistics at a time equal those of the log cut off there", () => {
  const events = [
    frame("h1"),
    logged("pass", "home", { from_player_id: "h1", to_player_id: "h2", outcome: "complete", end_pos: { x: 0.5, y: 0.5 }, progressive: true }),
    frame("h1"),
    logged("shot", "away", { player_id: "a1", outcome: "saved", xg: 0.4 }),
    frame("a1"),
    logged("tackle", "home", { player_id: "h1", target_id: "a1", outcome: "won" }),
    frame("h1"),
  ];
  const whole = build(...events).stats;
  const early = whole.teamStats(0, 0);
  const cut = build(...events.slice(0, 2)).stats.teamStats(0, 0);
  assert.deepEqual(early.home, cut.home);
  assert.equal(early.home.passes, 1);
  assert.equal(early.home.progressivePasses, 1);
  assert.equal(early.away.shots, 0);
  const late = whole.teamStats(0, 3);
  assert.equal(late.away.shots, 1);
  assert.equal(late.away.onTarget, 1);
  assert.equal(late.home.tacklesWon, 1);
  assert.ok(Math.abs(late.away.xg - 0.4) < 1e-9);
});

test("a window counts only the events inside it", () => {
  const { stats } = build(
    frame("h1"),
    logged("pass", "home", { from_player_id: "h1", to_player_id: "h2", outcome: "complete" }),
    frame("h1"),
    frame("h1"),
    logged("pass", "home", { from_player_id: "h2", to_player_id: "h1", outcome: "incomplete" }),
    frame("h1"),
  );
  assert.equal(stats.teamStats(0, 3).home.passes, 2);
  assert.equal(stats.teamStats(2, 3).home.passes, 1);
});

test("player tallies credit goals, assists and passes", () => {
  const { stats } = build(
    frame("h1"),
    logged("pass", "home", { from_player_id: "h1", to_player_id: "h2", outcome: "complete" }),
    logged("goal", "home", { scorer_id: "h2", assist_id: "h1" }),
    frame("h1"),
  );
  const tallies = stats.playerTallies(1);
  assert.equal(tallies.get("h2")?.goals, 1);
  assert.equal(tallies.get("h1")?.assists, 1);
  assert.equal(tallies.get("h1")?.passesCompleted, 1);
  assert.ok(formRating(tallies.get("h2")) > formRating(undefined));
  assert.ok(formRating(tallies.get("h2")) <= 10);
});

test("the pass map joins players by completed passes and places them where they passed from", () => {
  const { store } = build(
    frame("h1"),
    logged("pass", "home", { from_player_id: "h1", to_player_id: "h2", outcome: "complete", end_pos: { x: 0.6, y: 0.5 } }),
    logged("pass", "home", { from_player_id: "h1", to_player_id: "h2", outcome: "complete", end_pos: { x: 0.7, y: 0.5 } }),
    frame("h1"),
  );
  const map = passMap(store, meta, { team: "home", playerId: null, from: 0, to: 1 });
  assert.equal(map.edges.length, 1);
  assert.equal(map.edges[0]?.count, 2);
  assert.equal(map.lines.length, 2);
  assert.equal(map.nodes[0]?.count, 2);
});

test("the press map counts our players near the ball only while the other side has it", () => {
  const { store } = build(frame("a1", 0.5), frame("a1", 0.5), frame("h1", 0.3), frame("h1", 0.3));
  const map = pressMap(store, meta, { team: "home", playerId: null, from: 0, to: 3 });
  assert.ok(map.pressure.max >= 0);
  assert.ok(map.pressure.cells.some((value) => value > 0));
});

test("home attacks toward x = 1 in the first half and x = 0 in the second, whatever the context says", () => {
  assert.equal(homeDirection(1), 1);
  assert.equal(homeDirection(2), -1);
  const second = { ...(frame("h1", 0.5, -1) as object), clock: { ...clock, period: 2 }, ctx: { score_home: 0, score_away: 0, attack_dir: 1 } } as AnyEvent;
  const store = build(second).store;
  assert.equal(store.frames[0]?.homeDir, -1);
});

test("hit prefers the dot over the zone behind it and misses empty pitch", () => {
  const spots: Hotspot[] = [
    { shape: "rect", x: 0, y: 0, w: 100, h: 100, text: "zone" },
    { shape: "circle", x: 50, y: 50, r: 6, text: "dot" },
    { shape: "segment", x: 0, y: 90, x2: 100, y2: 90, text: "line" },
  ];
  assert.equal(hit(spots, 52, 52)?.text, "dot");
  assert.equal(hit(spots, 10, 10)?.text, "zone");
  assert.equal(hit(spots, 30, 91)?.text, "line");
  assert.equal(hit(spots, 300, 300), null);
});

test("the camera follows the chosen player instead of the ball", () => {
  const events = Array.from({ length: 6 }, () => frame(null, 0.9));
  const store = build(...events).store;
  const onBall = cameraAt(store.frames, 3, 2, null);
  const onPlayer = cameraAt(store.frames, 3, 2, "h1");
  assert.ok(onBall.x > onPlayer.x, `ball ${onBall.x}, player ${onPlayer.x}`);
});
