import assert from "node:assert/strict";
import { test } from "node:test";
import type { AnyEvent } from "./events.ts";
import { sampleAt } from "./interpolate.ts";
import { posesAt } from "./poses.ts";
import { project, sideCameraX } from "./sideview.ts";
import { SKILL_MOVES, SKILL_MOVE_S, isSkillMove, skillFrame } from "./skillposes.ts";
import { MatchStore } from "./store.ts";

const clock = { period: 1, minute: 0, second: 0, stoppage: 0 };

function frame(x: number, ballX: number, vx = 5): AnyEvent {
  return {
    type: "frame",
    team: "none",
    clock,
    ctx: { score_home: 0, score_away: 0, attack_dir: 1 },
    participants: [],
    pos: null,
    ball_pos_x: ballX,
    ball_pos_y: 0.5,
    carrier_id: null,
    players: [{ player_id: "a", x, y: 0.7, speed_mps: 5, vx, vy: 0, exhaustion: 0 }],
  } as AnyEvent;
}

test("the far touchline is higher on screen and smaller than the near one", () => {
  const far = project("broadcast", 0.5, 0.5, 0);
  const near = project("broadcast", 0.5, 0.5, 1);
  assert.ok(far.y < near.y);
  assert.ok(far.ppm < near.ppm);
  assert.ok(Math.abs(far.ppm / near.ppm - 0.62) < 1e-9);
});

test("depth spaces the rows the way a camera does: more pixels per row of pitch near the camera", () => {
  const rows = [0, 0.25, 0.5, 0.75, 1].map((y) => project("broadcast", 0.5, 0.5, y).y);
  const gaps = rows.slice(1).map((value, index) => value - (rows[index] ?? 0));
  for (let index = 1; index < gaps.length; index++) assert.ok((gaps[index] ?? 0) > (gaps[index - 1] ?? 0));
});

test("the point the camera looks at is the middle of the screen, and a height lifts a point up", () => {
  const ground = project("broadcast", 0.4, 0.4, 0.5);
  assert.equal(ground.x, 160);
  const lifted = project("broadcast", 0.4, 0.4, 0.5, 2);
  assert.ok(lifted.y < ground.y);
  assert.ok(Math.abs(ground.y - lifted.y - 2 * ground.ppm) < 1e-9);
});

test("the camera follows the ball along the pitch but stays inside it, and the wide shot does not pan", () => {
  const store = new MatchStore();
  for (let step = 0; step < 6; step++) store.onEvent(frame(0.5, 0.97));
  const followed = sideCameraX(store.frames, 3, "broadcast", null);
  assert.ok(followed > 0.5 && followed < 0.97);
  assert.equal(sideCameraX(store.frames, 3, "wide", null), 0.5);
  const focused = sideCameraX(store.frames, 3, "broadcast", "a");
  assert.ok(Math.abs(focused - 0.5) < 0.2, `player at 0.5, camera at ${focused}`);
});

test("every skill move starts and ends close to a plain run, and each does its own thing to the ball", () => {
  for (const move of SKILL_MOVES) {
    const start = skillFrame(move, 0);
    assert.ok(Math.hypot(start.ballAlong, start.ballAcross, start.ballLift) < 1e-9, `${move} starts with the ball at his feet`);
  }
  assert.ok(skillFrame("nutmeg", 0.4).ballAlong > 5);
  assert.ok(skillFrame("rainbow_flick", 0.5).ballLift > 8);
  assert.ok(skillFrame("drag_back", 0.3).ballAlong < -3);
  assert.ok(skillFrame("cut_inside", 0.4).ballAcross > 5);
  assert.equal(skillFrame("roulette", 0.5).turn, -1);
  assert.equal(skillFrame("roulette", 0.05).turn, 1);
  assert.equal(skillFrame("step_over", 0.2).profile, "feint");
});

test("no skill move leaves the player or the ball displaced when it ends, and none moves a body more than a metre", () => {
  for (const move of SKILL_MOVES) {
    const end = skillFrame(move, 1);
    assert.ok(Math.hypot(end.along, end.across, end.ballAlong, end.ballAcross, end.ballLift) < 1e-9, `${move} ends clean`);
    for (let step = 0; step <= 40; step++) {
      const frame = skillFrame(move, step / 40);
      assert.ok(Math.hypot(frame.along, frame.across) <= 3.5, `${move} moves his body ${Math.hypot(frame.along, frame.across)} px`);
      if (step < 40) {
        const next = skillFrame(move, (step + 1) / 40);
        assert.ok(Math.hypot(next.ballAlong - frame.ballAlong, next.ballAcross - frame.ballAcross) < 4, `${move} ball jumps at ${step}`);
      }
    }
  }
});

test("a recorded skill move poses the dribbler for its length and a plain run keeps the old sway", () => {
  const store = new MatchStore();
  for (let step = 0; step < 4; step++) store.onEvent(frame(0.5, 0.5));
  store.onEvent({ type: "dribble", team: "home", clock, ctx: { score_home: 0, score_away: 0, attack_dir: 1 }, participants: [], pos: null, player_id: "a", outcome: "success", skill_move: "nutmeg" } as AnyEvent);
  const sample = sampleAt(store.frames, 3.5);
  const during = posesAt(store.contests, sample, 3 + SKILL_MOVE_S / 2, store.frames).get("a");
  assert.ok(during !== undefined && Math.abs(during.ballDx ?? 0) > 3, "the ball is knocked ahead");
  assert.equal(during?.profile === undefined, false);
  assert.equal(posesAt(store.contests, sample, 3 + SKILL_MOVE_S + 0.1, store.frames).has("a"), false);
  assert.equal(isSkillMove("nutmeg"), true);
  assert.equal(isSkillMove("moonwalk"), false);
});
