import assert from "node:assert/strict";
import { test } from "node:test";
import { CARRY_AHEAD_M, MOVE_SECONDS, playMove, touchTimes } from "./choreo.ts";
import { bootPosition } from "./figure.ts";
import { SKILL_MOVES } from "./skillposes.ts";

const STEP = 1 / 60;
const phaseAt = (s: number): number => s / 0.62;
const AMP = 0.7;

function frames(move: (typeof SKILL_MOVES)[number]): ReturnType<typeof playMove>[] {
  const out = [];
  for (let s = 0; s <= MOVE_SECONDS + 1e-9; s += STEP) out.push(playMove(move, s, phaseAt(s), AMP));
  return out;
}

test("every move starts and ends as a normal dribble: body on the carrier, ball at his feet, defender released", () => {
  for (const move of SKILL_MOVES) {
    const start = playMove(move, 0, 0, AMP);
    const end = playMove(move, MOVE_SECONDS, phaseAt(MOVE_SECONDS), AMP);
    assert.ok(Math.hypot(start.attacker.f, start.attacker.l) < 1e-6, `${move} starts on the carrier`);
    assert.ok(Math.abs(start.ball.f - CARRY_AHEAD_M) < 1e-6 && Math.abs(start.ball.l) < 1e-6, `${move} starts with the ball at his feet`);
    assert.equal(start.defender.w, 0, `${move} starts with the defender where the replay has him`);
    assert.ok(Math.hypot(end.attacker.f, end.attacker.l) < 1e-6, `${move} ends on the carrier`);
    assert.ok(Math.abs(end.ball.f - CARRY_AHEAD_M) < 1e-6 && Math.abs(end.ball.l) < 1e-6, `${move} ends with the ball at his feet`);
    assert.equal(end.defender.w, 0, `${move} releases the defender`);
  }
});

test("the ball never jumps and the body never lurches", () => {
  for (const move of SKILL_MOVES) {
    const all = frames(move);
    all.slice(1).forEach((now, index) => {
      const before = all[index] as ReturnType<typeof playMove>;
      const ball = Math.hypot(now.ball.f - before.ball.f, now.ball.l - before.ball.l, (now.ball.h - before.ball.h) * 0.5);
      assert.ok(ball < 0.22, `${move}: the ball moves ${ball.toFixed(2)} m in one step at ${(index * STEP).toFixed(2)} s`);
      const body = Math.hypot(now.attacker.f - before.attacker.f, now.attacker.l - before.attacker.l) / STEP;
      assert.ok(body < 3.6, `${move}: the body moves ${body.toFixed(1)} m/s relative to the run at ${(index * STEP).toFixed(2)} s`);
    });
  }
});

test("a touch is a boot on the ball: at each touch time the ball is exactly where the boot is", () => {
  for (const move of SKILL_MOVES) {
    for (const time of touchTimes(move)) {
      const play = playMove(move, time, phaseAt(time), AMP);
      assert.ok(play.touching !== null, `${move} reports a touch at ${time}`);
      const sign = play.attacker.turn ? -1 : 1;
      const boot = bootPosition(play.attacker.joints, play.touching ?? "near", "tip");
      const sole = bootPosition(play.attacker.joints, play.touching ?? "near", "sole");
      const ankle = bootPosition(play.attacker.joints, play.touching ?? "near", "ankle");
      const distances = [boot, sole, ankle].map((place) => Math.abs(play.ball.f - (play.attacker.f + sign * place.forward)));
      assert.ok(Math.min(...distances) < 1e-6, `${move} at ${time}: the ball is ${Math.min(...distances)} m from the boot`);
    }
  }
});

test("the ball is independent of the player: it is a long way from his feet for much of every move", () => {
  for (const move of SKILL_MOVES) {
    const away = frames(move).filter((play) => Math.hypot(play.ball.f - play.attacker.f - CARRY_AHEAD_M, play.ball.l - play.attacker.l) > 0.45 || play.ball.h > 0.6).length;
    assert.ok(away > 15, `${move}: the ball is apart from the carried position for only ${away} frames`);
  }
});

test("a nutmeg sends the ball through the defender's legs and a rainbow flick over his head", () => {
  const nutmeg = frames("nutmeg");
  const through = nutmeg.filter((play) => play.defender.w > 0.9 && Math.hypot(play.ball.f - play.defender.f, play.ball.l - play.defender.l) < 0.45);
  assert.ok(through.length >= 2, "the ball passes the defender's feet while his legs are apart");
  assert.ok(nutmeg.every((play) => play.ball.h < 0.5), "a nutmeg stays on the grass");
  const flick = frames("rainbow_flick");
  const over = flick.filter((play) => play.ball.h > 1.6 && Math.abs(play.ball.f - play.defender.f) < 0.5);
  assert.ok(over.length >= 2, "the ball is above head height as it passes the defender");
});

test("the defender never walks through the carrier", () => {
  for (const move of SKILL_MOVES) {
    for (const play of frames(move)) {
      if (play.defender.w < 0.5) continue;
      const gap = Math.hypot(play.defender.f - play.attacker.f, play.defender.l - play.attacker.l);
      assert.ok(gap > 0.5, `${move}: the defender is ${gap.toFixed(2)} m from the carrier`);
    }
  }
});
