import { BALL_RADIUS_M, CARRY_AHEAD_M, MIN_GAP_M, bodyAt, ballAt, defenderAt, type BallKey, type BodyKey, type DefenderKey, type Lying, type Script } from "./choreo.ts";
import { STANCES, bootPosition, type StanceName } from "./figure.ts";
import { MOVE_SCRIPTS } from "./choreo.ts";
import type { SkillMoveName } from "./skillposes.ts";

// More scenes in the same language as the skill moves: the way a challenge ends a take-on or a
// plain run with the ball, a header, and a free kick. All in metres in the carrier's frame (f forward,
// l inside, h up), measured from his real place in the replay.

/** Which way the defender comes at the carrier: from the front (1), or chasing him from behind (-1). */
export type Approach = 1 | -1;

/** A defender chasing from behind runs level with the carrier's hip, this far to the side, not on his back. */
const BEHIND_SIDE_M = 0.8;

/** How a challenge on the carrier ends. */
export type ChallengeMode = "won" | "foul" | "lost" | "missed" | "slide_won" | "slide_foul";

export const CHALLENGE_MODES: readonly ChallengeMode[] = ["won", "missed", "foul", "slide_won", "slide_foul", "lost"];

/** How far a thrust-out boot reaches from where the tackler stands. */
const REACH_M = bootPosition(STANCES.tackleReach, "near", "tip").forward;
const PHASE = 0;
const AMP = 0.7;

/** The base of every challenge: a plain run with the ball, a defender closing in. */
export const CARRY_SCRIPT: Script = {
  duration: 1.8,
  owner: "attacker",
  body: [
    { s: 0, w: 0 },
    { s: 1.8, w: 0 },
  ],
  ball: [
    { s: 0, f: CARRY_AHEAD_M, l: 0 },
    { s: 0.01, carried: true },
    { s: 1.8, carried: true },
  ],
  defender: [
    { s: 0, w: 0, f: 3.0, l: 0.1, stance: "jockey" },
    { s: 0.4, w: 0.9, f: 2.2, l: 0.05, stance: "jockey" },
    { s: 0.55, w: 0.9, f: 1.9, l: 0.05, stance: "jockey" },
    { s: 1.8, w: 0.9, f: 1.9, l: 0.05, stance: "jockey" },
  ],
};

/** How long after the base scene's `from` a challenge takes to play out. */
const AFTER_S = 1.3;

const smoothStep = (u: number): number => u * u * (3 - 2 * u);

interface Snapshot {
  body: { f: number; l: number; h: number; stance: StanceName | undefined; w: number; turn: boolean; lying: Lying | null };
  ball: { f: number; l: number; h: number };
  defender: DefenderKey;
}

function nearerKey<T extends { s: number }>(keys: readonly T[], s: number): T {
  let best = keys[0] as T;
  for (const key of keys) if (Math.abs(key.s - s) < Math.abs(best.s - s)) best = key;
  return best;
}

function snapshotAt(base: Script, from: number): Snapshot {
  const body = bodyAt(base, from, PHASE, AMP);
  const key = nearerKey(base.body, from);
  const before = [...base.body].filter((k) => k.s <= from).pop() as BodyKey;
  const after = base.body.find((k) => k.s > from) ?? before;
  const span = after.s - before.s;
  const u = span <= 0 ? 0 : (from - before.s) / span;
  const w = before.w + (after.w - before.w) * smoothStep(u);
  const defender = defenderAt(base, from);
  const defenderKey = nearerKey(base.defender, from);
  return {
    body: { f: body.f, l: body.l, h: body.h, stance: key.stance, w, turn: body.turn, lying: body.lying },
    ball: ballAt(base, from, PHASE, AMP),
    defender: { s: from, w: defender.w, f: defender.f, l: defender.l, h: defender.h, stance: defenderKey.stance, turn: defender.turn, lying: defender.lying ?? undefined },
  };
}

/** The base scene cut off at `from`, so a challenge can take over from the state it had reached. */
function truncated(base: Script, from: number): { body: BodyKey[]; ball: BallKey[]; defender: DefenderKey[]; snap: Snapshot } {
  const snap = snapshotAt(base, from);
  const body: BodyKey[] = base.body.filter((key) => key.s < from - 1e-6);
  body.push({ s: from, w: snap.body.w, stance: snap.body.stance, f: snap.body.f, l: snap.body.l, h: snap.body.h, turn: snap.body.turn, lying: snap.body.lying ?? undefined });
  const ball: BallKey[] = base.ball.filter((key) => key.s < from - 1e-6);
  ball.push({ s: from, f: snap.ball.f, l: snap.ball.l, h: snap.ball.h });
  const defender: DefenderKey[] = base.defender.filter((key) => key.s < from - 1e-6);
  defender.push(snap.defender);
  return { body, ball, defender, snap };
}

/**
 * A challenge made on the carrier `from` seconds into a base scene (a skill move or a plain run).
 * The base plays until then; after it the defender strikes and the scene ends as `mode` says.
 * `d` is the way he comes: from the front he stands beyond the ball and reaches back to it; from
 * behind he stands short of it, level with the carrier's hip, and reaches forward.
 */
function buildChallenge(base: Script, from: number, mode: ChallengeMode, d: Approach): Script {
  const { body, ball, defender: carried, snap } = truncated(base, from);
  const bf = snap.ball.f;
  const bl = snap.ball.l;
  const bodyF = snap.body.f;
  // Coming from the front, the base's own defender carries on. Coming from behind, the base's defender
  // (who is ahead of the carrier, being beaten) is not the man who tackles, so he is a chaser from three metres back.
  const defender: DefenderKey[] =
    d > 0
      ? carried.map((key) => ({ ...key }))
      : [
          { s: 0, w: 0, f: -3.2, l: 0, stance: "jockey" },
          { s: Math.max(from, 0.1), w: 0.9, f: bodyF - 1.6, l: 0, stance: "jockey" },
        ];
  // A slide starts from where he already is, so he does not jump to its start.
  const here = defender[defender.length - 1] as DefenderKey;
  const slideFrom = here.f;
  // He finishes on the side of the carrier he came in on, so his path never has to cut across the carrier.
  const lean = (fallback: 1 | -1): number => (Math.abs(here.l - bl) > 0.2 ? Math.sign(here.l - bl) : fallback);
  // He meets the ball at the carrier's front, never inside the carrier himself.
  const slideTo = d > 0 ? Math.max(bf + 0.12, bodyF + MIN_GAP_M) : Math.min(bf - 0.12, bodyF - MIN_GAP_M);
  // If the spot he first strikes from is too far to lunge to in time, the whole challenge starts a little later.
  const strike = firstStrike(mode, bf, bl, bodyF, d, here);
  const delay = Math.max(Math.hypot(strike.f - here.f, strike.l - here.l) / LUNGE_MPS - strike.after, 0);
  const end = from + delay + AFTER_S;
  const at = (x: number): number => from + delay + x;
  const contactAt = at(CONTACT_AFTER_S[mode]);
  switch (mode) {
    case "won": {
      // A firm tackle: the near boot thrust through the ball, which runs on to the tackler.
      defender.push({ s: at(0.22), w: 1, f: bf + d * REACH_M, l: bl, stance: "tackleReach" });
      const out = lean(1);
      defender.push({ s: at(0.6), w: 1, f: bf + d * 0.55, l: bl + out * 0.5, stance: "ready" });
      defender.push({ s: end, w: 0.9, f: bf + d * 0.55, l: bl + out * 0.5, stance: "ready" });
      ball.push({ s: at(0.22), f: bf, l: bl, h: BALL_RADIUS_M });
      ball.push({ s: at(0.62), f: bf + d * 0.35, l: bl + out * 0.6, ease: "out" });
      ball.push({ s: end, f: bf + d * 0.35, l: bl + out * 0.6 });
      body.push({ s: at(0.22), w: 0.9, stance: "stumble", f: bodyF, l: snap.body.l });
      body.push({ s: at(0.6), w: 0.4, f: bodyF - 0.1, l: snap.body.l });
      body.push({ s: end, w: 0, f: 0, l: 0 });
      return finished({ duration: end, owner: "defender", body, ball, defender, contactAt }, d);
    }
    case "missed": {
      // The lunge is a mistimed: the carrier hops it and the defender goes past, off balance.
      defender.push({ s: at(0.2), w: 1, f: bf + d * REACH_M, l: bl, stance: "tackleReach" });
      const past = lean(1);
      defender.push({ s: at(0.45), w: 1, f: bf - d * 0.2, l: bl + past * 0.7, stance: "stumble" });
      defender.push({ s: end, w: 0, f: bf - d * 0.2, l: bl + past * 0.7, stance: "stumble" });
      body.push({ s: at(0.18), w: 1, stance: "hop", f: bodyF + 0.1, l: snap.body.l, h: 0.3 });
      body.push({ s: at(0.4), w: 0.3, f: bodyF + 0.3, l: snap.body.l, h: 0 });
      body.push({ s: end, w: 0, f: 0, l: 0, h: 0 });
      ball.push({ s: at(0.4), carried: true });
      ball.push({ s: end, carried: true });
      return finished({ duration: end, owner: "attacker", body, ball, defender, contactAt }, d);
    }
    case "foul": {
      // A clumsy lunge catches the legs: the carrier goes down, the ball runs loose.
      defender.push({ s: at(0.14), w: 1, f: bf + d * REACH_M, l: bl, stance: "tackleReach" });
      const into = lean(-1);
      defender.push({ s: at(0.3), w: 1, f: bf + d * 0.4, l: bl + into * 0.5, stance: "tackleReach", lying: "slide" });
      defender.push({ s: end, w: 1, f: bf - d * 0.4, l: bl + into * 0.7, stance: "tackleReach", lying: "slide" });
      body.push({ s: at(0.22), w: 1, stance: "stumble", f: bodyF, l: snap.body.l });
      body.push({ s: at(0.55), w: 1, stance: "stumble", f: bodyF + 0.5, l: snap.body.l + 0.35, lying: "forward" });
      body.push({ s: end, w: 1, stance: "stumble", f: bodyF + 0.6, l: snap.body.l + 0.4, lying: "forward" });
      ball.push({ s: end, f: bf + 0.9, l: bl + 0.2, ease: "out" });
      return finished({ duration: end, owner: "none", body, ball, defender, contactAt }, d);
    }
    case "lost": {
      // A heavy touch: the ball runs away ahead and the defender steps on to it.
      const px = bf + 1.1;
      const pl = bl + 0.9;
      ball.push({ s: at(0.7), f: px, l: pl, ease: "out" });
      ball.push({ s: end, f: px, l: pl });
      defender.push({ s: at(0.3), w: 1, f: px + d * 1.1, l: pl, stance: "ready" });
      defender.push({ s: at(0.7), w: 1, f: px + d * REACH_M, l: pl, stance: "tackleReach" });
      defender.push({ s: end, w: 0.8, f: px + d * REACH_M, l: pl, stance: "tackleReach" });
      body.push({ s: at(0.2), w: 0.9, stance: "kickNear", f: bodyF + 0.1, l: snap.body.l });
      body.push({ s: at(0.6), w: 0.3, f: bodyF + 0.3, l: snap.body.l });
      body.push({ s: end, w: 0, f: 0, l: 0 });
      return finished({ duration: end, owner: "defender", body, ball, defender, contactAt }, d);
    }
    case "slide_won": {
      // A sliding tackle from a few strides away: feet first through the ball while the carrier hops it.
      defender.push({ s: at(0.08), w: 1, f: slideFrom, l: here.l, stance: "tackleReach", lying: "slide" });
      defender.push({ s: at(0.34), w: 1, f: slideTo, l: bl, stance: "tackleReach", lying: "slide" });
      const through = lean(1);
      defender.push({ s: at(0.8), w: 1, f: bf - d * 0.5, l: bl + through * 0.9, stance: "tackleReach", lying: "slide" });
      defender.push({ s: end, w: 0.9, f: bf - d * 0.5, l: bl + through * 0.9, stance: "tackleReach", lying: "slide" });
      ball.push({ s: at(0.34), f: bf, l: bl, h: BALL_RADIUS_M });
      ball.push({ s: at(0.8), f: bf - d * 0.35, l: bl + through * 0.5, ease: "out" });
      ball.push({ s: end, f: bf - d * 0.35, l: bl + through * 0.5 });
      body.push({ s: at(0.24), w: 1, stance: "hop", f: bodyF + 0.1, l: snap.body.l, h: 0.3 });
      body.push({ s: at(0.5), w: 0.4, f: bodyF + 0.25, l: snap.body.l, h: 0 });
      body.push({ s: end, w: 0, f: 0, l: 0, h: 0 });
      return finished({ duration: end, owner: "defender", body, ball, defender, contactAt }, d);
    }
    case "slide_foul": {
      // The slide arrives late and takes the carrier's legs.
      defender.push({ s: at(0.08), w: 1, f: slideFrom, l: here.l, stance: "tackleReach", lying: "slide" });
      const under = lean(-1);
      defender.push({ s: at(0.3), w: 1, f: slideTo, l: bl + under * 0.5, stance: "tackleReach", lying: "slide" });
      defender.push({ s: end, w: 1, f: bf - d * 0.7, l: bl + under * 0.8, stance: "tackleReach", lying: "slide" });
      body.push({ s: at(0.26), w: 1, stance: "stumble", f: bodyF, l: snap.body.l });
      body.push({ s: at(0.58), w: 1, stance: "stumble", f: bodyF + 0.5, l: snap.body.l + 0.35, lying: "forward" });
      body.push({ s: end, w: 1, stance: "stumble", f: bodyF + 0.55, l: snap.body.l + 0.4, lying: "forward" });
      ball.push({ s: end, f: bf + 0.9, l: bl + 0.3, ease: "out" });
      return finished({ duration: end, owner: "none", body, ball, defender, contactAt }, d);
    }
  }
}

/** The most a defender lunges at, metres a second: farther than that and the challenge waits for him to arrive. */
const LUNGE_MPS = 6;

/** Where, and how soon after the challenge starts, the defender first strikes (or, in a slide, meets the ball). */
function firstStrike(mode: ChallengeMode, bf: number, bl: number, bodyF: number, d: Approach, here: DefenderKey): { f: number; l: number; after: number } {
  switch (mode) {
    case "won":
      return { f: bf + d * REACH_M, l: bl, after: 0.22 };
    case "missed":
      return { f: bf + d * REACH_M, l: bl, after: 0.2 };
    case "foul":
      return { f: bf + d * REACH_M, l: bl, after: 0.14 };
    case "lost":
      return { f: bf + 1.1 + d * 1.1, l: bl + 0.9, after: 0.3 };
    case "slide_won":
      return { f: d > 0 ? Math.max(bf + 0.12, bodyF + MIN_GAP_M) : Math.min(bf - 0.12, bodyF - MIN_GAP_M), l: bl, after: 0.34 };
    case "slide_foul":
      return { f: d > 0 ? Math.max(bf + 0.1, bodyF + MIN_GAP_M) : Math.min(bf - 0.1, bodyF - MIN_GAP_M), l: bl + (Math.abs(here.l - bl) > 0.2 ? Math.sign(here.l - bl) : -1) * 0.5, after: 0.3 };
  }
}

/** A defender coming from behind faces the way the carrier runs, and stands to the side of him. */
function finished(script: Script, d: Approach): Script {
  if (d > 0) return script;
  return { ...script, defender: script.defender.map((key) => ({ ...key, l: key.l + BEHIND_SIDE_M, turn: true })) };
}

/** Seconds after the defender starts his challenge that the ball changes hands or the carrier goes down. */
const CONTACT_AFTER_S: Record<ChallengeMode, number> = { won: 0.22, missed: 0.2, foul: 0.14, lost: 0.7, slide_won: 0.34, slide_foul: 0.3 };

/**
 * A challenge made on the carrier `from` seconds into a base scene (a skill move or a plain run).
 * The base plays until then; after it the defender strikes and the scene ends as `mode` says.
 */
export function challengeScript(base: Script, from: number, mode: ChallengeMode, d: Approach = 1): Script {
  return buildChallenge(base, from, mode, d);
}

/** A challenge on a plain run with the ball, made `from` seconds in. */
export function tackleScript(mode: ChallengeMode, d: Approach = 1): Script {
  return challengeScript(CARRY_SCRIPT, 0.55, mode, d);
}

/** When the defender strikes in each skill move (seconds in), for a move that fails. */
export const MOVE_CHALLENGE_AT: Record<SkillMoveName, number> = {
  knock_past: 0.55,
  step_over: 0.7,
  drag_back: 0.7,
  cut_inside: 0.6,
  nutmeg: 0.5,
  roulette: 0.6,
  rainbow_flick: 0.6,
};

/** A skill move that fails: it plays until the defender gets a boot in, then the challenge ends it. */
export function failedMove(move: SkillMoveName, mode: ChallengeMode, d: Approach = 1): Script {
  return challengeScript(MOVE_SCRIPTS[move], MOVE_CHALLENGE_AT[move], mode, d);
}

/**
 * The script with `lead` seconds of plain running put in front of it, over which the defender can
 * come in from wherever he is. Every key moves later; his pull toward the scene is spread over the
 * longer approach so he is never asked to cover the ground faster than a man can run.
 */
export function withLeadIn(script: Script, lead: number): Script {
  if (lead <= 0) return script;
  const later = <T extends { s: number }>(keys: T[]): T[] => keys.map((key) => ({ ...key, s: key.s + lead }));
  const first = script.defender[0] as DefenderKey;
  const second = script.defender[1] ?? first;
  const ramp = Math.max(second.s - first.s, 1e-6);
  return {
    ...script,
    duration: script.duration + lead,
    contactAt: script.contactAt === undefined ? undefined : script.contactAt + lead,
    ballFrom: script.ballFrom === undefined ? undefined : script.ballFrom + lead,
    ballUntil: script.ballUntil === undefined ? undefined : script.ballUntil + lead,
    body: [{ ...(script.body[0] as BodyKey), s: 0 }, ...later(script.body)],
    ball: [{ ...(script.ball[0] as BallKey), s: 0 }, ...later(script.ball)],
    // He heads for the spot the script first wants him at from the start, at the pace the original ramp gave.
    defender: [{ ...second, s: 0, w: first.w }, { ...second, s: lead, w: first.w + ((second.w - first.w) * lead) / (lead + ramp) }, ...later(script.defender.slice(1))],
  };
}

/** Which side of the carrier a script stands its defender on once the scene is under way: 1 inside, -1 outside. */
export function defenderSide(script: Script): 1 | -1 {
  const from = (script.contactAt ?? 0) - 0.2;
  let total = 0;
  for (const key of script.defender) if (key.s >= from) total += key.l * key.w;
  return total >= 0 ? 1 : -1;
}

/** When the head meets the ball in a header scene, seconds in. */
export const HEADER_CONTACT_S = 0.88;

/** A header: a short run and a leap, the ball met at the top of the jump and sent on (or cleared back). */
export function headerScript(kind: "shot" | "clear"): Script {
  const sign = kind === "shot" ? 1 : -1;
  const turn = kind === "clear";
  return {
    duration: 2.0,
    owner: "none",
    ballFrom: 0.4,
    ballUntil: HEADER_CONTACT_S + 0.02,
    body: [
      { s: 0, w: 0, f: -1.1 * sign, turn },
      { s: 0.5, w: 0, f: -0.1 * sign, h: 0, turn },
      { s: 0.62, w: 1, stance: "headerJump", f: 0.05 * sign, h: 0.25, turn },
      { s: 0.88, w: 1, stance: "headerSwing", f: 0.22 * sign, h: 0.62, turn },
      { s: 1.15, w: 0.5, stance: "hop", f: 0.35 * sign, h: 0.2, turn },
      { s: 1.4, w: 0.3, f: 0.35 * sign, h: 0, turn },
      { s: 2.0, w: 0, f: 0, h: 0, turn: false },
    ],
    ball: [
      { s: 0, f: -3.2 * sign, l: -9.5, h: 1.2 },
      { s: HEADER_CONTACT_S, f: 0.62 * sign, l: 0, h: 2.3, arc: 1.6, ease: "linear" },
      { s: 1.4, f: 6.5 * sign, l: kind === "shot" ? 0.6 : -2.5, h: kind === "shot" ? 1.3 : 3.2, arc: kind === "shot" ? 0.4 : 1.5, ease: "linear" },
      { s: 2.0, f: 11 * sign, l: kind === "shot" ? 0.9 : -4, h: BALL_RADIUS_M, ease: "out" },
    ],
    defender: [
      { s: 0, w: 0, f: 0.4, l: 0.8, stance: "jockey", turn: kind === "shot" },
      { s: 0.5, w: 1, f: 0.35 * sign, l: 0.85, stance: "jockey", turn: kind === "shot" },
      { s: 0.78, w: 1, f: 0.45 * sign, l: 0.85, stance: "hop", h: 0.35, turn: kind === "shot" },
      { s: 1.1, w: 1, f: 0.5 * sign, l: 0.85, stance: "hop", h: 0.05, turn: kind === "shot" },
      { s: 1.5, w: 0.6, f: 0.5 * sign, l: 0.85, stance: "stumble", turn: kind === "shot" },
      { s: 2.0, w: 0, f: 0.5 * sign, l: 0.85, stance: "stumble", turn: kind === "shot" },
    ],
  };
}

/** Where the taker stands so the toe of his kicking boot meets the ball where it lies. */
const STRIKE_F = -bootPosition(STANCES.freeKickStrike, "near", "tip").forward;

/** When the boot meets the ball in a kick scene, seconds in. */
export const KICK_TOUCH_S = 2.7;

/** A dead-ball kick: the taker steps back `back` metres, turns, waits, runs up and strikes it over the wall. */
export function kickScript(back: number): Script {
  return {
  duration: 3.6,
  owner: "none",
  ballUntil: KICK_TOUCH_S + 0.02,
  body: [
    { s: 0, w: 0, f: 0 },
    { s: 0.15, w: 0, f: 0, turn: true },
    { s: 1.0, w: 0, f: -back, turn: true },
    { s: 1.15, w: 1, stance: "hips", f: -back, turn: false },
    { s: 1.8, w: 1, stance: "hips", f: -back, turn: false },
    { s: 1.85, w: 0.5, stance: "ready", f: -back },
    { s: 2.55, w: 0, f: STRIKE_F - 0.1 },
    { s: 2.7, w: 1, stance: "freeKickStrike", f: STRIKE_F },
    { s: 2.9, w: 1, stance: "freeKickFollow", f: STRIKE_F + 0.65 },
    { s: 3.3, w: 0.3, f: 0.1 },
    { s: 3.6, w: 0, f: 0 },
  ],
  ball: [
    { s: 0, f: 0, l: 0, h: BALL_RADIUS_M },
    { s: KICK_TOUCH_S - 0.01, f: 0, l: 0, h: BALL_RADIUS_M },
    { s: KICK_TOUCH_S, touch: { foot: "near", where: "tip" } },
    { s: 3.15, f: 8.5, l: 1.4, h: 2.0, arc: 0.7, ease: "out" },
    { s: 3.6, f: 14, l: 1.9, h: 1.0, arc: 0.3, ease: "out" },
  ],
  // The wall, standing 9 m away, jumps as the ball is struck (its place is the replay's own).
  defender: [
    { s: 0, w: 0, f: 9.15, l: 0, stance: "jockey" },
    { s: 2.6, w: 0, f: 9.15, l: 0, stance: "jockey", stanceW: 0 },
    { s: 2.8, w: 0, f: 9.15, l: 0, stance: "hop", h: 0.5, stanceW: 1 },
    { s: 3.1, w: 0, f: 9.15, l: 0, stance: "hop", h: 0.05, stanceW: 0.6 },
    { s: 3.6, w: 0, f: 9.15, l: 0, stance: "jockey", stanceW: 0 },
  ],
  };
}

/** A direct free kick: the taker steps back four metres. */
export const FREE_KICK_SCRIPT: Script = kickScript(4.0);
