import { STANCES, blendJoints, bootPosition, swing, type Joints, type StanceName } from "./figure.ts";
import type { SkillMoveName } from "./skillposes.ts";

// Scenes as choreography. Everything is in metres in the runner's own frame, measured from the real
// carrier position in the replay: `f` is forward along his run, `l` toward the middle of the pitch
// and `h` up. The ball is its own object: it follows a player only where a key says it is carried,
// and wherever a boot touches it the ball is placed on that boot (taken from the pose's skeleton),
// so every touch is a real contact and every roll in between is the ball on its own.

export const MOVE_SECONDS = 1.8;
/** How far ahead of a running carrier the replay normally keeps the ball. */
export const CARRY_AHEAD_M = 0.9;
export const BALL_RADIUS_M = 0.11;

/** How a figure lies on the grass: after a fall forward, or sliding in feet first. */
export type Lying = "forward" | "slide";

export interface BodyKey {
  s: number;
  /** How far into `stance` he is: 0 is plain running, 1 the stance itself. */
  w: number;
  stance?: StanceName;
  f?: number;
  l?: number;
  /** Height off the ground in metres (a jump). */
  h?: number;
  /** Turned round (facing against his running) from this key on. */
  turn?: boolean;
  lying?: Lying;
}

export type Ease = "smooth" | "out" | "linear";

export interface BallKey {
  s: number;
  /** On this boot at this moment (a touch). */
  touch?: { foot: "near" | "far"; where?: "tip" | "sole" | "ankle" };
  /** Carried at his feet as in a normal dribble. */
  carried?: boolean;
  f?: number;
  l?: number;
  h?: number;
  /** An arc up and down over the segment ending at this key, peak height in metres. */
  arc?: number;
  /** How the ball moves from the previous key to this one. */
  ease?: Ease;
}

export interface DefenderKey {
  s: number;
  /** How far he is pulled from where the replay has him to `f`, `l` (0 not at all, 1 fully). */
  w: number;
  f: number;
  l: number;
  h?: number;
  stance: StanceName;
  /** How far into `stance` his body is, when that should differ from how far he is pulled (a wall that jumps in place). */
  stanceW?: number;
  turn?: boolean;
  lying?: Lying;
}

export type Owner = "attacker" | "defender" | "none";

export interface Script {
  duration: number;
  body: BodyKey[];
  ball: BallKey[];
  defender: DefenderKey[];
  /** Who has the ball when the scene ends. */
  owner: Owner;
  /** When the ball changes hands or the carrier goes down, in seconds into the scene (for lining it up with the replay). */
  contactAt?: number;
  /** The ball follows the script only from this time (before it the replay's own ball is shown). */
  ballFrom?: number;
  /** The ball follows the script only until this time (a shot or a kick then takes over). */
  ballUntil?: number;
}

export const MOVE_SCRIPTS: Record<SkillMoveName, Script> = {
  // The ball is knocked ahead with the toe and he bursts after it.
  knock_past: {
    duration: MOVE_SECONDS,
    owner: "attacker",
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
  // A double step-over: each foot swung over a ball that does not move, then a push the other way.
  step_over: {
    duration: MOVE_SECONDS,
    owner: "attacker",
    body: [
      { s: 0, w: 0 },
      { s: 0.16, w: 1, stance: "stepOverRaise", f: 0.1, l: 0.05 },
      { s: 0.3, w: 1, stance: "stepOverPlant", f: 0.2, l: 0.3 },
      { s: 0.44, w: 1, stance: "stepOverRaiseFar", f: 0.25, l: 0.3 },
      { s: 0.58, w: 1, stance: "stepOverPlantFar", f: 0.3, l: 0.1 },
      { s: 0.84, w: 1, stance: "kickNear", f: 0.35, l: -0.3 },
      { s: 1.15, w: 0.3, f: 0.6, l: -0.55 },
      { s: 1.8, w: 0, f: 0, l: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.84, touch: { foot: "near", where: "tip" } },
      { s: 1.15, f: 2.0, l: -1.1, ease: "out" },
      { s: 1.4, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.0, l: 0, stance: "jockey" },
      { s: 0.25, w: 0.8, f: 1.9, l: 0, stance: "jockey" },
      { s: 0.38, w: 0.9, f: 1.9, l: 0.5, stance: "jockey" },
      { s: 0.56, w: 0.9, f: 1.9, l: 0.1, stance: "jockey" },
      { s: 0.9, w: 0.9, f: 1.7, l: 0.85, stance: "stumble" },
      { s: 1.8, w: 0, f: 1.7, l: 0.85, stance: "stumble" },
    ],
  },
  // The sole stops the ball and draws it back; he slows, then drives it on as the defender lunges past.
  drag_back: {
    duration: MOVE_SECONDS,
    owner: "attacker",
    body: [
      { s: 0, w: 0 },
      { s: 0.3, w: 1, stance: "soleOnBall", f: 0.05 },
      { s: 0.62, w: 1, stance: "soleBack", f: -0.45 },
      { s: 0.95, w: 1, stance: "kickNear", f: -0.2 },
      { s: 1.25, w: 0.2, f: 0.4 },
      { s: 1.8, w: 0, f: 0 },
    ],
    ball: [
      { s: 0, f: CARRY_AHEAD_M, l: 0 },
      { s: 0.3, touch: { foot: "near", where: "sole" } },
      { s: 0.62, touch: { foot: "near", where: "sole" }, ease: "smooth" },
      { s: 0.95, touch: { foot: "near", where: "tip" } },
      { s: 1.25, f: 1.5, l: 0, ease: "out" },
      { s: 1.45, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.2, l: 0, stance: "jockey" },
      { s: 0.3, w: 0.8, f: 1.8, l: 0, stance: "jockey" },
      { s: 0.65, w: 0.9, f: 1.3, l: 0.35, stance: "tackleReach" },
      { s: 1.0, w: 0.9, f: 1.2, l: 0.85, stance: "stumble" },
      { s: 1.8, w: 0, f: 1.2, l: 0.85, stance: "stumble" },
    ],
  },
  // The shoulder dropped, the ball taken across the body and off at an angle.
  cut_inside: {
    duration: MOVE_SECONDS,
    owner: "attacker",
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
  // A poke along the grass between the defender's open legs (the ball passes behind his near leg,
  // so it shows in the gap), then round him to collect it.
  nutmeg: {
    duration: MOVE_SECONDS,
    owner: "attacker",
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
      { s: 0.5, f: 1.7, l: 0.3, ease: "linear" },
      { s: 0.78, f: 2.35, l: 0.3, ease: "linear" },
      { s: 1.05, f: 2.05, l: 0.05, ease: "out" },
      { s: 1.15, carried: true },
      { s: 1.8, carried: true },
    ],
    defender: [
      { s: 0, w: 0, f: 2.05, l: 0, stance: "jockey" },
      { s: 0.2, w: 1, f: 2.05, l: 0, stance: "legsApart" },
      { s: 0.85, w: 1, f: 2.05, l: 0, stance: "legsApart" },
      { s: 1.1, w: 0.8, f: 1.7, l: 0.5, stance: "stumble", turn: true },
      { s: 1.8, w: 0, f: 1.7, l: 0.5, stance: "stumble", turn: true },
    ],
  },
  // The ball rolled back with the sole as he spins on the other foot, then pushed out the other way.
  roulette: {
    duration: MOVE_SECONDS,
    owner: "attacker",
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
    duration: MOVE_SECONDS,
    owner: "attacker",
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

/** What one moment of a scene looks like, in the runner's frame (metres from the real carrier). */
export interface MovePlay {
  attacker: { f: number; l: number; h: number; joints: Joints; turn: boolean; lying: Lying | null };
  ball: { f: number; l: number; h: number };
  /** Which boot has the ball at this instant, if a touch is happening. */
  touching: "near" | "far" | null;
  /** The defender: where he is pulled to (relative to the carrier), how strongly, and how he stands. */
  defender: { w: number; stanceW: number; f: number; l: number; h: number; joints: Joints; turn: boolean; lying: Lying | null };
  /** Who has the ball once the scene is over. */
  owner: Owner;
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

function lerp(a: number | undefined, b: number | undefined, u: number): number {
  const from = a ?? b ?? 0;
  const to = b ?? a ?? 0;
  return from + (to - from) * u;
}

/** A body key's value, taken from the nearest earlier key that states it (omitted means unchanged). */
function held(keys: readonly BodyKey[], key: BodyKey, field: "f" | "l" | "h"): number {
  for (let at = keys.indexOf(key); at >= 0; at--) {
    const value = keys[at]?.[field];
    if (value !== undefined) return value;
  }
  return 0;
}

export interface BodyState {
  f: number;
  l: number;
  h: number;
  turn: boolean;
  lying: Lying | null;
  joints: Joints;
}

export function bodyAt(script: Script, s: number, phase: number, amp: number): BodyState {
  const keys = script.body;
  const { a, b, u } = between(keys, s);
  const run = swing(phase, amp);
  const jointsOf = (key: BodyKey): Joints => (key.stance === undefined ? run : blendJoints(run, STANCES[key.stance], key.w));
  const k = smooth(u);
  const nearer = u < 0.5 ? a : b;
  return {
    f: lerp(held(keys, a, "f"), held(keys, b, "f"), k),
    l: lerp(held(keys, a, "l"), held(keys, b, "l"), k),
    h: lerp(held(keys, a, "h"), held(keys, b, "h"), k),
    turn: nearer.turn === true,
    lying: nearer.lying ?? null,
    joints: blendJoints(jointsOf(a), jointsOf(b), k),
  };
}

type Place = { f: number; l: number; h: number };

function ballPlace(script: Script, key: BallKey, previous: Place, phase: number, amp: number): Place {
  if (key.touch !== undefined) {
    const body = bodyAt(script, key.s, phase, amp);
    const boot = bootPosition(body.joints, key.touch.foot, key.touch.where ?? "tip");
    const sign = body.turn ? -1 : 1;
    return { f: body.f + sign * boot.forward, l: body.l, h: key.touch.where === "sole" ? BALL_RADIUS_M : Math.max(BALL_RADIUS_M, body.h + boot.height) };
  }
  if (key.carried === true) {
    const body = bodyAt(script, key.s, phase, amp);
    return { f: body.f + CARRY_AHEAD_M, l: body.l, h: BALL_RADIUS_M };
  }
  return { f: key.f ?? previous.f, l: key.l ?? previous.l, h: key.h ?? BALL_RADIUS_M };
}

export function ballAt(script: Script, s: number, phase: number, amp: number): Place {
  const keys = script.ball;
  const { a, b, u } = between(keys, s);
  const placeA = ballPlace(script, a, { f: CARRY_AHEAD_M, l: 0, h: BALL_RADIUS_M }, phase, amp);
  const placeB = ballPlace(script, b, placeA, phase, amp);
  const eased = b.ease === "out" ? 1 - (1 - u) * (1 - u) * (1 - u) : b.ease === "linear" ? u : smooth(u);
  const arc = (b.arc ?? 0) * 4 * u * (1 - u);
  return {
    f: placeA.f + (placeB.f - placeA.f) * eased,
    l: placeA.l + (placeB.l - placeA.l) * eased,
    h: placeA.h + (placeB.h - placeA.h) * eased + arc,
  };
}

export function defenderAt(script: Script, s: number): MovePlay["defender"] {
  const { a, b, u } = between(script.defender, s);
  const k = smooth(u);
  const nearer = u < 0.5 ? a : b;
  return {
    w: a.w + (b.w - a.w) * k,
    stanceW: lerp(a.stanceW ?? a.w, b.stanceW ?? b.w, k),
    f: a.f + (b.f - a.f) * k,
    l: a.l + (b.l - a.l) * k,
    h: lerp(a.h, b.h, k),
    joints: blendJoints(STANCES[a.stance], STANCES[b.stance], k),
    turn: nearer.turn === true,
    lying: nearer.lying ?? null,
  };
}

/** Swap the near and far limbs: the same move done with the other foot. */
export function mirrorJoints(J: Joints): Joints {
  return { bob: J.bob, lean: J.lean, near: J.far, far: J.near, nearArm: J.farArm, farArm: J.nearArm };
}

const TOUCH_WINDOW_S = 0.05;
/** How long after a scene a beaten defender takes to get his balance back. */
export const DEFENDER_RECOVERY_S = 0.6;

function touchAt(script: Script, s: number): "near" | "far" | null {
  for (const key of script.ball) {
    if (key.touch !== undefined && Math.abs(key.s - s) <= TOUCH_WINDOW_S) return key.touch.foot;
  }
  return null;
}

export type Foot = "near" | "far";

/**
 * A script `s` seconds in. `phase` and `amp` are the carrier's stride (so his legs keep running when
 * no stance is holding them). With `foot` "far" the move is done with the other foot: the same
 * script with the legs swapped, so every touch is still exactly on a boot. At the end the body is at
 * the carrier's real place, the ball where `script.owner` says and the defender where the replay has him.
 */
export function playScript(script: Script, s: number, phase: number, amp: number, foot: Foot = "near"): MovePlay {
  // For a moment after the end the beaten defender is still off balance, then he is just running again.
  const fade = s > script.duration ? Math.max(0, 1 - (s - script.duration) / DEFENDER_RECOVERY_S) : 1;
  const at = Math.min(Math.max(s, 0), script.duration);
  const body = bodyAt(script, at, phase, amp);
  const ball = ballAt(script, at, phase, amp);
  const touching = touchAt(script, at);
  const defender = defenderAt(script, at);
  return {
    attacker: { f: body.f, l: body.l, h: body.h, turn: body.turn, lying: body.lying, joints: foot === "far" ? mirrorJoints(body.joints) : body.joints },
    ball,
    touching: touching === null ? null : foot === "far" ? (touching === "near" ? "far" : "near") : touching,
    defender: { ...defender, stanceW: defender.stanceW * fade },
    owner: script.owner,
  };
}

/** The closest two players in a scene are allowed to stand (their bodies are about a metre across). */
export const MIN_GAP_M = 0.9;

/**
 * Keep the defender from standing inside the carrier: if they are closer than `MIN_GAP_M` he is put
 * on a circle that far round him. The direction leans toward his `side` (1 inside, -1 outside; by
 * default the side he is on) the closer he is, so a defender whose path runs through the carrier
 * swings round him on that side instead of being thrown from one side to the other in a frame.
 */
export function keepApart(play: MovePlay, side?: 1 | -1, minimum = MIN_GAP_M): MovePlay {
  const df = play.defender.f - play.attacker.f;
  const dl = play.defender.l - play.attacker.l;
  const gap = Math.hypot(df, dl);
  if (gap >= minimum || play.defender.w < 0.05) return play;
  const lean = side ?? (dl >= 0 ? 1 : -1);
  const toward = { f: df, l: dl + lean * (minimum - gap) };
  const length = Math.hypot(toward.f, toward.l);
  const away = length < 1e-6 ? { f: 0, l: lean } : { f: toward.f / length, l: toward.l / length };
  return { ...play, defender: { ...play.defender, f: play.attacker.f + away.f * minimum, l: play.attacker.l + away.l * minimum } };
}

/** A skill move `s` seconds in (see `playScript`). */
export function playMove(move: SkillMoveName, s: number, phase: number, amp: number, foot: Foot = "near"): MovePlay {
  return playScript(MOVE_SCRIPTS[move], s, phase, amp, foot);
}

/** The times a boot meets the ball in a script (for sound and for review). */
export function touchTimes(script: Script | SkillMoveName): number[] {
  const keys = (typeof script === "string" ? MOVE_SCRIPTS[script] : script).ball;
  return keys.filter((key) => key.touch !== undefined).map((key) => key.s);
}
