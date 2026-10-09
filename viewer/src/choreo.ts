import { STANCES, blendJoints, bootPosition, swing, type Joints, type StanceName } from "./figure.ts";
import type { SkillMoveName } from "./skillposes.ts";

// Skill moves as choreography. Everything is in metres in the runner's own frame, measured from the
// real carrier position in the replay: `f` is forward along his run and `l` is toward the middle of
// the pitch. The ball is its own object: it only follows the player where a key says it is carried,
// and wherever a foot touches it the ball is placed on that foot (taken from the pose's skeleton), so
// every touch is a real contact and every roll in between is the ball on its own.

export const MOVE_SECONDS = 1.8;
/** How far ahead of a running carrier the replay normally keeps the ball. */
export const CARRY_AHEAD_M = 0.9;
const BALL_RADIUS_M = 0.11;

interface BodyKey {
  s: number;
  /** How far into `stance` he is: 0 is plain running, 1 the stance itself. */
  w: number;
  stance?: StanceName;
  f?: number;
  l?: number;
  /** Turned round (facing against his running) from this key on. */
  turn?: boolean;
}

type Ease = "smooth" | "out" | "linear";

interface BallKey {
  s: number;
  /** On this boot at this moment (a touch). */
  touch?: { foot: "near" | "far"; where?: "tip" | "sole" | "ankle" };
  /** Carried at his feet as in a normal dribble. */
  carried?: boolean;
  f?: number;
  l?: number;
  /** An arc up and down over the segment ending at this key, peak height in metres. */
  arc?: number;
  /** How the ball moves from the previous key to this one. */
  ease?: Ease;
}

interface DefenderKey {
  s: number;
  /** How far he is pulled from where the replay has him to `f`, `l` (0 not at all, 1 fully). */
  w: number;
  f: number;
  l: number;
  stance: StanceName;
  turn?: boolean;
}

interface Script {
  body: BodyKey[];
  ball: BallKey[];
  defender: DefenderKey[];
}

const SCRIPTS: Record<SkillMoveName, Script> = {
  // The ball is knocked ahead with the toe and he bursts after it.
  knock_past: {
    body: [
      { s: 0, w: 0 },
      { s: 0.16, w: 1, stance: "kickNear", f: 0.05 },
      { s: 0.36, w: 0.25, f: 0.2 },
      { s: 0.75, w: 0, f: 0.6 },
      { s: 1.1, w: 0, f: 0.6 },
      { s: 1.8, w: 0, f: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.16, touch: { foot: "near", where: "tip" } },
      { s: 0.7, f: 2.0, l: 0.1, ease: "out" },
      { s: 1.12, f: 1.6, l: 0.1, ease: "out" },
      { s: 1.25, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.4, l: 0, stance: "jockey" },
      { s: 0.2, w: 0.7, f: 2.4, l: -0.2, stance: "jockey" },
      { s: 0.6, w: 0.8, f: 2.1, l: -0.8, stance: "stumble" },
      { s: 1.8, w: 0, f: 2.1, l: -0.8, stance: "stumble" },
    ],
  },
  // A foot swung over the ball one way, then the other foot drives it the other way.
  step_over: {
    body: [
      { s: 0, w: 0 },
      { s: 0.22, w: 1, stance: "stepOverRaise", f: 0.05, l: 0.05 },
      { s: 0.5, w: 1, stance: "stepOverPlant", f: 0.1, l: 0.35 },
      { s: 0.8, w: 1, stance: "strike", f: 0.2, l: -0.2 },
      { s: 1.1, w: 0.3, f: 0.5, l: -0.5 },
      { s: 1.8, w: 0, f: 0, l: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.8, touch: { foot: "far", where: "tip" } },
      { s: 1.15, f: 1.9, l: -1.0, ease: "out" },
      { s: 1.35, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.0, l: 0, stance: "jockey" },
      { s: 0.25, w: 0.8, f: 1.9, l: 0, stance: "jockey" },
      { s: 0.55, w: 0.9, f: 1.9, l: 0.55, stance: "stumble" },
      { s: 1.0, w: 0.9, f: 1.7, l: 1.0, stance: "stumble" },
      { s: 1.8, w: 0, f: 1.7, l: 1.0, stance: "stumble" },
    ],
  },
  // The sole stops the ball and draws it back under him; the defender lunges at it and is left behind.
  drag_back: {
    body: [
      { s: 0, w: 0 },
      { s: 0.3, w: 1, stance: "soleOnBall", f: 0.15 },
      { s: 0.62, w: 1, stance: "soleBack", f: -0.05 },
      { s: 0.95, w: 1, stance: "kickNear", f: 0.15 },
      { s: 1.2, w: 0.2, f: 0.55 },
      { s: 1.8, w: 0, f: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.3, touch: { foot: "near", where: "sole" } },
      { s: 0.62, touch: { foot: "near", where: "sole" }, ease: "smooth" },
      { s: 0.95, touch: { foot: "near", where: "tip" } },
      { s: 1.25, f: 1.6, l: 0, ease: "out" },
      { s: 1.45, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.2, l: 0, stance: "jockey" },
      { s: 0.3, w: 0.8, f: 1.7, l: 0, stance: "jockey" },
      { s: 0.65, w: 0.9, f: 1.25, l: 0.35, stance: "stumble" },
      { s: 1.0, w: 0.9, f: 1.2, l: 0.8, stance: "stumble" },
      { s: 1.8, w: 0, f: 1.2, l: 0.8, stance: "stumble" },
    ],
  },
  // The shoulder dropped, the ball taken across the body with the far foot and off at an angle.
  cut_inside: {
    body: [
      { s: 0, w: 0 },
      { s: 0.3, w: 1, stance: "cutReach", f: 0.15, l: 0.05 },
      { s: 0.6, w: 0.6, f: 0.3, l: 0.5 },
      { s: 1.0, w: 0, f: 0.5, l: 0.9 },
      { s: 1.8, w: 0, f: 0, l: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.3, touch: { foot: "near", where: "tip" } },
      { s: 0.75, f: 1.5, l: 1.4, ease: "out" },
      { s: 1.0, f: 1.6, l: 1.5, ease: "out" },
      { s: 1.15, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.1, l: 0, stance: "jockey" },
      { s: 0.3, w: 0.8, f: 1.9, l: -0.1, stance: "jockey" },
      { s: 0.65, w: 0.9, f: 1.8, l: -0.7, stance: "stumble" },
      { s: 1.1, w: 0.9, f: 1.6, l: -1.2, stance: "stumble" },
      { s: 1.8, w: 0, f: 1.6, l: -1.2, stance: "stumble" },
    ],
  },
  // A poke through the defender's legs, then round him to collect it.
  nutmeg: {
    body: [
      { s: 0, w: 0 },
      { s: 0.28, w: 1, stance: "kickNear", f: 0.1 },
      { s: 0.5, w: 0.2, f: 0.3, l: -0.1 },
      { s: 1.0, w: 0, f: 0.9, l: -0.5 },
      { s: 1.8, w: 0, f: 0, l: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.28, touch: { foot: "near", where: "tip" } },
      { s: 0.7, f: 2.05, l: 0, ease: "linear" },
      { s: 1.05, f: 2.55, l: -0.15, ease: "out" },
      { s: 1.15, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.05, l: 0, stance: "jockey" },
      { s: 0.2, w: 1, f: 2.05, l: 0, stance: "legsApart" },
      { s: 0.85, w: 1, f: 2.05, l: 0, stance: "legsApart" },
      { s: 1.1, w: 0.8, f: 1.7, l: 0.4, stance: "stumble", turn: true },
      { s: 1.8, w: 0, f: 1.7, l: 0.4, stance: "stumble", turn: true },
    ],
  },
  // The ball rolled back with the sole as he spins on the other foot, then pushed out the other way.
  roulette: {
    body: [
      { s: 0, w: 0 },
      { s: 0.25, w: 1, stance: "soleOnBall", f: 0.1 },
      { s: 0.55, w: 1, stance: "pivot", f: -0.1, turn: true },
      { s: 0.9, w: 1, stance: "pivot", f: 0, turn: true },
      { s: 1.0, w: 1, stance: "strike", f: 0.05, turn: false },
      { s: 1.35, w: 0.2, f: 0.6, l: -0.2 },
      { s: 1.8, w: 0, f: 0, l: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.25, touch: { foot: "near", where: "sole" } },
      { s: 0.55, touch: { foot: "near", where: "sole" }, ease: "smooth" },
      { s: 0.78, f: 0.25, l: 0.35, ease: "smooth" },
      { s: 1.0, touch: { foot: "far", where: "tip" } },
      { s: 1.3, f: 1.7, l: -0.35, ease: "out" },
      { s: 1.5, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.2, l: 0.8, stance: "jockey" },
      { s: 0.3, w: 0.8, f: 1.9, l: 0.8, stance: "jockey" },
      { s: 0.8, w: 0.8, f: 1.7, l: 0.8, stance: "jockey" },
      { s: 1.1, w: 0.9, f: 1.3, l: 1.0, stance: "stumble" },
      { s: 1.8, w: 0, f: 1.3, l: 1.0, stance: "stumble" },
    ],
  },
  // The ball trapped between the heels and flicked up and over his own head and the defender's.
  rainbow_flick: {
    body: [
      { s: 0, w: 0 },
      { s: 0.3, w: 0.8, stance: "ready", f: 0.1 },
      { s: 0.45, w: 1, stance: "heelFlick", f: 0.25 },
      { s: 0.75, w: 0.7, stance: "watch", f: 0.55 },
      { s: 1.05, w: 0, f: 0.95 },
      { s: 1.8, w: 0, f: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.3, f: 0.05, l: 0, ease: "smooth" },
      { s: 0.45, touch: { foot: "near", where: "ankle" } },
      { s: 1.1, f: 2.3, l: 0, arc: 2.5, ease: "linear" },
      { s: 1.2, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.0, l: 0, stance: "jockey" },
      { s: 0.45, w: 0.9, f: 1.9, l: 0, stance: "jockey" },
      { s: 0.85, w: 0.9, f: 1.8, l: 0, stance: "watch" },
      { s: 1.2, w: 0.9, f: 1.2, l: 0.5, stance: "stumble", turn: true },
      { s: 1.8, w: 0, f: 1.2, l: 0.5, stance: "stumble", turn: true },
    ],
  },
};

/** What one moment of a skill move looks like, in the runner's frame (metres from the real carrier). */
export interface MovePlay {
  attacker: { f: number; l: number; joints: Joints; turn: boolean };
  ball: { f: number; l: number; h: number };
  /** Which boot has the ball at this instant, if a touch is happening. */
  touching: "near" | "far" | null;
  /** The defender: where he is pulled to (relative to the carrier), how strongly, and how he stands. */
  defender: { w: number; f: number; l: number; joints: Joints; turn: boolean };
}

const smooth = (u: number): number => u * u * (3 - 2 * u);
const clamp01 = (u: number): number => Math.min(Math.max(u, 0), 1);

function between<T extends { s: number }>(keys: readonly T[], s: number): { a: T; b: T; u: number } {
  let index = 0;
  while (index < keys.length - 2 && (keys[index + 1]?.s ?? Infinity) <= s) index++;
  const a = keys[index] as T;
  const b = keys[index + 1] as T;
  const span = b.s - a.s;
  return { a, b, u: span <= 0 ? 1 : clamp01((s - a.s) / span) };
}

function number(a: number | undefined, b: number | undefined, u: number): number {
  const from = a ?? b ?? 0;
  const to = b ?? a ?? 0;
  return from + (to - from) * u;
}

function bodyAt(script: Script, s: number, phase: number, amp: number): { f: number; l: number; turn: boolean; joints: Joints } {
  const keys = script.body;
  const { a, b, u } = between(keys, s);
  const run = swing(phase, amp);
  const jointsOf = (key: BodyKey): Joints => (key.stance === undefined ? run : blendJoints(run, STANCES[key.stance], key.w));
  const turnOf = (key: BodyKey): boolean => key.turn === true;
  return {
    f: number(fillF(keys, a), fillF(keys, b), smooth(u)),
    l: number(fillL(keys, a), fillL(keys, b), smooth(u)),
    turn: u < 0.5 ? turnOf(a) : turnOf(b),
    joints: blendJoints(jointsOf(a), jointsOf(b), smooth(u)),
  };
}

/** A key's forward offset, defaulting to the previous key's (so omitted means "unchanged"). */
function fillF(keys: readonly BodyKey[], key: BodyKey): number {
  const index = keys.indexOf(key);
  for (let at = index; at >= 0; at--) {
    const value = keys[at]?.f;
    if (value !== undefined) return value;
  }
  return 0;
}

function fillL(keys: readonly BodyKey[], key: BodyKey): number {
  const index = keys.indexOf(key);
  for (let at = index; at >= 0; at--) {
    const value = keys[at]?.l;
    if (value !== undefined) return value;
  }
  return 0;
}

/** Where a ball key puts the ball: on a boot, carried at his feet, or at the stated spot. */
function ballPlace(script: Script, key: BallKey, previous: { f: number; l: number }, phase: number, amp: number): { f: number; l: number; h: number } {
  if (key.touch !== undefined) {
    const body = bodyAt(script, key.s, phase, amp);
    const boot = bootPosition(body.joints, key.touch.foot, key.touch.where ?? "tip");
    const sign = body.turn ? -1 : 1;
    return { f: body.f + sign * boot.forward, l: body.l, h: key.touch.where === "sole" ? BALL_RADIUS_M : Math.max(BALL_RADIUS_M, boot.height) };
  }
  if (key.carried === true) {
    const body = bodyAt(script, key.s, phase, amp);
    return { f: body.f + CARRY_AHEAD_M, l: body.l, h: BALL_RADIUS_M };
  }
  return { f: key.f ?? previous.f, l: key.l ?? previous.l, h: BALL_RADIUS_M };
}

function ballAt(script: Script, s: number, phase: number, amp: number): { f: number; l: number; h: number } {
  const keys = script.ball;
  const { a, b, u } = between(keys, s);
  const placeA = ballPlace(script, a, { f: CARRY_AHEAD_M, l: 0 }, phase, amp);
  const placeB = ballPlace(script, b, placeA, phase, amp);
  const eased = b.ease === "out" ? 1 - (1 - u) * (1 - u) * (1 - u) : b.ease === "linear" ? u : smooth(u);
  const arc = (b.arc ?? 0) * 4 * u * (1 - u);
  return {
    f: placeA.f + (placeB.f - placeA.f) * eased,
    l: placeA.l + (placeB.l - placeA.l) * eased,
    h: placeA.h + (placeB.h - placeA.h) * eased + arc,
  };
}

function defenderAt(script: Script, s: number): MovePlay["defender"] {
  const { a, b, u } = between(script.defender, s);
  const k = smooth(u);
  const stance = (key: DefenderKey): Joints => STANCES[key.stance];
  return {
    w: a.w + (b.w - a.w) * k,
    f: a.f + (b.f - a.f) * k,
    l: a.l + (b.l - a.l) * k,
    joints: blendJoints(stance(a), stance(b), k),
    turn: u < 0.5 ? a.turn === true : b.turn === true,
  };
}

/**
 * The move `move` `s` seconds in. `phase` and `amp` are the carrier's stride (so his legs keep
 * running when no stance is holding them). At the end of the move the body is at the carrier's real
 * place, the ball at his feet and the defender where the replay has him.
 */
export function playMove(move: SkillMoveName, s: number, phase: number, amp: number): MovePlay {
  const script = SCRIPTS[move];
  const at = Math.min(Math.max(s, 0), MOVE_SECONDS);
  const body = bodyAt(script, at, phase, amp);
  const ball = ballAt(script, at, phase, amp);
  const touching = touchAt(script, at);
  return { attacker: { f: body.f, l: body.l, joints: body.joints, turn: body.turn }, ball, touching, defender: defenderAt(script, at) };
}

const TOUCH_WINDOW_S = 0.05;

function touchAt(script: Script, s: number): "near" | "far" | null {
  for (const key of script.ball) {
    if (key.touch !== undefined && Math.abs(key.s - s) <= TOUCH_WINDOW_S) return key.touch.foot;
  }
  return null;
}

/** The times a boot meets the ball in a move (for sound and for review). */
export function touchTimes(move: SkillMoveName): number[] {
  return SCRIPTS[move].ball.filter((key) => key.touch !== undefined).map((key) => key.s);
}
