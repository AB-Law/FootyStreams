import { sampleAt, type Sample } from "./interpolate.ts";
import { toScreen } from "./pitch.ts";
import type { ProfilePose } from "./profile.ts";
import { SKILL_MOVE_S, skillFrame } from "./skillposes.ts";
import type { Contest, Frame } from "./store.ts";

export type PoseName = "stand" | "slide" | "fall" | "throw";

/** How one player is shown right now: a pose, a shift in world pixels and which way he faces. */
export interface Pose {
  name: PoseName;
  dx: number;
  dy: number;
  /** +1 when the action points to the right of the screen, -1 to the left. */
  facing: 1 | -1;
  /** False when the ball stays where it is while the player moves (a run-up to a dead ball). */
  ballFollows?: boolean;
  /** How high the player holds the ball, in pixels (a throw-in). */
  ballLift?: number;
  /** Where the ball is, beyond the shift it shares with the player (a skill move), in pixels. */
  ballDx?: number;
  ballDy?: number;
  /** The side-on pose and the way he faces (-1 turns him against his running, mid-roulette). */
  profile?: ProfilePose;
  turn?: 1 | -1;
}

/** How long a contest plays, in match seconds (so it is quick at 4x and 16x, as everything is). */
const TACKLE_S = 1.1;
const DRIBBLE_S = 0.9;
const FALL_S = 2.2;
/** The tackler goes in over this share of the move, and is on the ground for the middle of it. */
const LUNGE_SHARE = 0.35;
const SLIDE_FROM = 0.1;
const SLIDE_TO = 0.8;
const DODGE_PX = 5;
const LUNGE_REACH = 0.85;
const STUMBLE_PX = 3;
const FALL_FROM = 0.3;

type Point = { x: number; y: number };

function place(sample: Sample, id: string): Point | null {
  const player = sample.players.find((candidate) => candidate.id === id);
  return player === undefined ? null : toScreen(player.x, player.y);
}

function unit(from: Point, to: Point): { x: number; y: number; length: number } {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  return { x: dx / length, y: dy / length, length };
}

function facing(dx: number): 1 | -1 {
  return dx >= 0 ? 1 : -1;
}

function tackle(contest: Extract<Contest, { kind: "tackle" }>, sample: Sample, t: number, out: Map<string, Pose>): void {
  const tackler = place(sample, contest.tacklerId);
  const target = place(sample, contest.targetId);
  if (tackler === null || target === null) return;
  const age = t - contest.t;
  const toward = unit(tackler, target);
  const progress = age / TACKLE_S;
  if (progress >= 0 && progress < 1) {
    const reach = Math.min(progress / LUNGE_SHARE, 1) * Math.max(toward.length * LUNGE_REACH, 0);
    const sliding = progress > SLIDE_FROM && progress < SLIDE_TO;
    out.set(contest.tacklerId, { name: sliding ? "slide" : "stand", dx: toward.x * reach, dy: toward.y * reach, facing: facing(toward.x) });
    const bump = Math.sin(Math.PI * progress);
    if (contest.outcome === "missed") {
      // The carrier rides the challenge: a sidestep across the line of the tackle.
      out.set(contest.targetId, { name: "stand", dx: -toward.y * DODGE_PX * bump, dy: toward.x * DODGE_PX * bump, facing: facing(-toward.x) });
    } else if (contest.outcome === "won") {
      out.set(contest.targetId, { name: "stand", dx: toward.x * STUMBLE_PX * bump, dy: toward.y * STUMBLE_PX * bump, facing: facing(toward.x) });
    }
  }
  if (contest.outcome === "foul" && age >= FALL_FROM * TACKLE_S && age < FALL_S) {
    out.set(contest.targetId, { name: "fall", dx: toward.x * STUMBLE_PX, dy: toward.y * STUMBLE_PX, facing: facing(toward.x) });
  }
}

/** A skill move: the player and the ball follow the move's shape along and across his running line. */
function skillMove(contest: Extract<Contest, { kind: "dribble" }>, move: NonNullable<Extract<Contest, { kind: "dribble" }>["move"]>, sample: Sample, t: number, out: Map<string, Pose>): void {
  const progress = (t - contest.t) / SKILL_MOVE_S;
  if (progress < 0 || progress >= 1) return;
  const player = sample.players.find((candidate) => candidate.id === contest.playerId);
  if (player === undefined) return;
  const speed = Math.hypot(player.vx, player.vy);
  const along = speed < 0.5 ? { x: 1, y: 0 } : { x: player.vx / speed, y: player.vy / speed };
  // Across is toward the middle of the pitch (the touchline-to-touchline axis is y).
  const perp = { x: -along.y, y: along.x };
  const toMiddle = player.y > 0.5 ? -1 : 1;
  const across = perp.y * toMiddle >= 0 ? perp : { x: -perp.x, y: -perp.y };
  const frame = skillFrame(move, progress);
  out.set(contest.playerId, {
    name: "stand",
    dx: along.x * frame.along + across.x * frame.across,
    dy: along.y * frame.along + across.y * frame.across,
    facing: along.x >= 0 ? 1 : -1,
    ballDx: along.x * frame.ballAlong + across.x * frame.ballAcross,
    ballDy: along.y * frame.ballAlong + across.y * frame.ballAcross,
    ballLift: frame.ballLift,
    profile: frame.profile,
    turn: frame.turn,
  });
}

function dribble(contest: Extract<Contest, { kind: "dribble" }>, sample: Sample, t: number, out: Map<string, Pose>): void {
  if (contest.move !== null) {
    skillMove(contest, contest.move, sample, t, out);
    return;
  }
  const progress = (t - contest.t) / DRIBBLE_S;
  if (progress < 0 || progress >= 1) return;
  const carrier = place(sample, contest.playerId);
  if (carrier === null) return;
  // A feint: out to one side and back, the way the take-on goes (side set by the carrier's place).
  const side = contest.playerId.length % 2 === 0 ? 1 : -1;
  const sway = Math.sin(2 * Math.PI * progress) * DODGE_PX * (contest.outcome === "success" ? 1 : 0.5);
  out.set(contest.playerId, { name: "stand", dx: 0, dy: sway * side, facing: 1 });
}

const RUN_UP_S = 1.4;
const AFTER_KICK_S = 0.5;
const RUN_UP_BACK_SHARE = 0.7;
const BACK_STEP_PX = 6;
const LUNGE_PX = 3;
const THROW_FROM_S = 0.8;
const THROW_LIFT_PX = 11;
/** A restart is kicked when the ball starts to move after standing still at least this long. */
const STILL_FOR_S = 3;
const STILL_METRES = 0.5;
const SEARCH_S = 70;

/** When the dead ball is played: where the ball, still since `from`, first moves again. */
export function kickTime(frames: readonly Frame[], from: number): number {
  let stillSince = -1;
  const last = Math.min(Math.floor(from) + SEARCH_S, frames.length - 2);
  for (let index = Math.max(Math.floor(from), 0); index <= last; index++) {
    const now = frames[index];
    const next = frames[index + 1];
    if (now === undefined || next === undefined) break;
    const moved = Math.hypot((next.ballX - now.ballX) * 105, (next.ballY - now.ballY) * 68);
    if (moved < STILL_METRES) {
      if (stillSince < 0) stillSince = index;
    } else if (stillSince >= 0 && index - stillSince >= STILL_FOR_S) {
      return index;
    } else {
      stillSince = -1;
    }
  }
  return from + 1;
}

function restart(contest: Extract<Contest, { kind: "restart" }>, sample: Sample, frames: readonly Frame[], t: number, out: Map<string, Pose>): void {
  const kick = kickTime(frames, contest.t);
  if (t < kick - RUN_UP_S || t > kick + AFTER_KICK_S) return;
  const taker = place(sample, contest.takerId);
  if (taker === null) return;
  if (contest.restart === "throw_in") {
    if (t >= kick - THROW_FROM_S) out.set(contest.takerId, { name: "throw", dx: 0, dy: 0, facing: 1, ballLift: THROW_LIFT_PX });
    return;
  }
  const after = sampleAt(frames, kick + 1);
  const target = after === null ? taker : toScreen(after.ballX, after.ballY);
  const toward = unit(taker, target);
  const run = (t - (kick - RUN_UP_S)) / RUN_UP_S;
  const back = Math.sin((Math.PI / 2) * Math.min(Math.max(run, 0) / RUN_UP_BACK_SHARE, 1));
  const lunge = run <= RUN_UP_BACK_SHARE ? 0 : Math.min((run - RUN_UP_BACK_SHARE) / (1 - RUN_UP_BACK_SHARE), 1);
  const along = -BACK_STEP_PX * back * (1 - lunge) + LUNGE_PX * lunge;
  const settle = t > kick ? Math.max(1 - (t - kick) / AFTER_KICK_S, 0) : 1;
  out.set(contest.takerId, { name: "stand", dx: toward.x * along * settle, dy: toward.y * along * settle, facing: facing(toward.x), ballFollows: false });
}

/** The poses of the players in a contest at `t`; everyone else just stands or runs. */
export function posesAt(contests: readonly Contest[], sample: Sample | null, t: number, frames: readonly Frame[] = []): Map<string, Pose> {
  const out = new Map<string, Pose>();
  if (sample === null) return out;
  for (let index = contests.length - 1; index >= 0; index--) {
    const contest = contests[index];
    if (contest === undefined) continue;
    if (contest.t > t && contest.kind !== "restart") continue;
    if (contest.t > t + SEARCH_S) continue;
    if (t - contest.t > FALL_S + (contest.kind === "restart" ? SEARCH_S : 0)) break;
    if (contest.kind === "tackle") tackle(contest, sample, t, out);
    else if (contest.kind === "dribble") dribble(contest, sample, t, out);
    else if (contest.kind === "restart") restart(contest, sample, frames, t, out);
  }
  return out;
}
