import assert from "node:assert/strict";
import { test } from "node:test";
import { MIN_GAP_M, ballAt, keepApart, playScript, type MovePlay, type Script } from "./choreo.ts";
import { CHALLENGE_MODES, FREE_KICK_SCRIPT, failedMove, headerScript, tackleScript } from "./scenes.ts";
import { SKILL_MOVES } from "./skillposes.ts";

const STEP = 1 / 60;

function all(script: Script, foot: "near" | "far" = "near"): MovePlay[] {
  const out: MovePlay[] = [];
  for (let s = 0; s <= script.duration + 1e-9; s += STEP) out.push(playScript(script, s, s / 0.62, 0.7, foot));
  return out;
}

test("a tackle ends the way its mode says: who has the ball, and who is on the ground", () => {
  const owners = { won: "defender", missed: "attacker", foul: "none", lost: "defender", slide_won: "defender", slide_foul: "none" } as const;
  for (const mode of CHALLENGE_MODES) {
    const end = all(tackleScript(mode)).at(-1) as MovePlay;
    assert.equal(end.owner, owners[mode], `${mode} owner`);
    const carrierDown = end.attacker.lying === "forward";
    assert.equal(carrierDown, mode === "foul" || mode === "slide_foul", `${mode}: the carrier is down only after a foul`);
    const sliding = end.defender.lying === "slide";
    assert.equal(sliding, mode === "foul" || mode === "slide_won" || mode === "slide_foul", `${mode}: slide`);
  }
});

test("a challenge that does not foul leaves the carrier on his real place, and a won ball runs to the tackler", () => {
  for (const mode of ["won", "missed", "lost", "slide_won"] as const) {
    const end = all(tackleScript(mode)).at(-1) as MovePlay;
    assert.ok(Math.hypot(end.attacker.f, end.attacker.l) < 1e-6, `${mode}: back on the carrier`);
    assert.ok(Math.abs(end.attacker.h) < 1e-6, `${mode}: back on the ground`);
  }
  const won = all(tackleScript("won")).at(-1) as MovePlay;
  assert.ok(Math.hypot(won.ball.f - won.defender.f, won.ball.l - won.defender.l) < 1.3, "the ball is at the tackler's feet");
});

test("every challenge, on a plain run and on each failed skill move, moves the ball and bodies smoothly", () => {
  const scripts: [string, Script][] = [];
  for (const mode of CHALLENGE_MODES) {
    scripts.push([`tackle ${mode}`, tackleScript(mode)]);
    for (const move of SKILL_MOVES) scripts.push([`${move} ${mode}`, failedMove(move, mode)]);
  }
  for (const [name, script] of scripts) {
    const frames = all(script);
    frames.slice(1).forEach((now, index) => {
      const before = frames[index] as MovePlay;
      const ball = Math.hypot(now.ball.f - before.ball.f, now.ball.l - before.ball.l, (now.ball.h - before.ball.h) * 0.5);
      assert.ok(ball < 0.3, `${name}: the ball moves ${ball.toFixed(2)} m at ${(index * STEP).toFixed(2)} s`);
      const body = Math.hypot(now.attacker.f - before.attacker.f, now.attacker.l - before.attacker.l) / STEP;
      assert.ok(body < 4.2, `${name}: the carrier moves ${body.toFixed(1)} m/s at ${(index * STEP).toFixed(2)} s`);
    });
  }
});

test("a header meets the ball at head height at the top of the jump and sends it toward goal, or clears it back", () => {
  const shot = headerScript("shot");
  const peak = playScript(shot, 0.88, 0, 0.7);
  assert.ok(peak.attacker.h > 0.5, "he is in the air");
  assert.ok(Math.abs(peak.ball.h - (peak.attacker.h + 1.7)) < 0.35, `the ball is at his head: ${peak.ball.h} against ${peak.attacker.h + 1.7}`);
  assert.ok(ballAt(shot, 1.8, 0, 0.7).f > ballAt(shot, 0.88, 0, 0.7).f + 4, "a shot goes toward goal");
  const clear = headerScript("clear");
  assert.ok(ballAt(clear, 1.8, 0, 0.7).f < ballAt(clear, 0.88, 0, 0.7).f - 4, "a clearance goes the other way");
  const end = playScript(shot, shot.duration, 0, 0.7);
  assert.ok(Math.hypot(end.attacker.f, end.attacker.h) < 1e-6, "he lands where the replay has him");
});

test("a free kick has the taker step back, turn, wait, run up and strike a ball that has not moved until his boot hits it", () => {
  const frames = all(FREE_KICK_SCRIPT);
  const struck = FREE_KICK_SCRIPT.ball.find((key) => key.touch !== undefined)?.s ?? 0;
  assert.ok(frames.filter((_, index) => index * STEP < struck - 0.01).every((play) => Math.hypot(play.ball.f, play.ball.l) < 1e-6), "the ball sits still");
  const back = frames.map((play) => play.attacker.f);
  assert.ok(Math.min(...back) < -3.5, "he walks back several strides");
  assert.ok(frames.some((play) => play.attacker.turn), "he turns away while walking back");
  const contact = playScript(FREE_KICK_SCRIPT, struck, 0, 1);
  assert.equal(contact.touching, "near");
  assert.ok(Math.abs(contact.ball.f) < 0.05, "the ball is struck where it lay");
  const wall = playScript(FREE_KICK_SCRIPT, struck + 0.12, 0, 1);
  assert.ok(wall.defender.stanceW > 0.5, "the wall jumps as the ball is struck");
});

test("every scene can be played with either foot, and each touch is still on a boot", () => {
  for (const mode of CHALLENGE_MODES) {
    const play = playScript(tackleScript(mode), 0.8, 1, 0.7, "far");
    assert.ok(Number.isFinite(play.ball.f));
  }
  const far = playScript(FREE_KICK_SCRIPT, FREE_KICK_SCRIPT.ball.find((key) => key.touch !== undefined)?.s ?? 0, 0, 1, "far");
  assert.equal(far.touching, "far");
});

test("no scene leaves the ball stranded or the players standing inside each other", () => {
  const scripts: [string, Script][] = [];
  for (const mode of CHALLENGE_MODES) {
    scripts.push([`tackle ${mode}`, tackleScript(mode)]);
    for (const move of SKILL_MOVES) scripts.push([`${move} ${mode}`, failedMove(move, mode)]);
  }
  for (const [name, script] of scripts) {
    for (const play of all(script).map((frame) => keepApart(frame))) {
      if (play.defender.w < 0.05) continue;
      const gap = Math.hypot(play.defender.f - play.attacker.f, play.defender.l - play.attacker.l);
      assert.ok(gap >= MIN_GAP_M - 1e-9, `${name}: the players are ${gap.toFixed(2)} m apart`);
    }
    const end = playScript(script, script.duration, 0, 0.7);
    const nearest = Math.min(Math.hypot(end.ball.f - end.attacker.f, end.ball.l - end.attacker.l), Math.hypot(end.ball.f - end.defender.f, end.ball.l - end.defender.l));
    assert.ok(nearest < 2.2, `${name}: the ball ends ${nearest.toFixed(2)} m from the nearest player`);
    if (end.owner === "defender") {
      const toDefender = Math.hypot(end.ball.f - end.defender.f, end.ball.l - end.defender.l);
      assert.ok(toDefender < 1.0, `${name}: the tackler is ${toDefender.toFixed(2)} m from the ball he won`);
    }
  }
});
