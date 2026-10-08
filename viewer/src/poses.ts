import type { Sample } from "./interpolate.ts";
import { toScreen } from "./pitch.ts";
import type { Contest } from "./store.ts";

export type PoseName = "stand" | "slide" | "fall";

/** How one player is shown right now: a pose, a shift in world pixels and which way he faces. */
export interface Pose {
  name: PoseName;
  dx: number;
  dy: number;
  /** +1 when the action points to the right of the screen, -1 to the left. */
  facing: 1 | -1;
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

function dribble(contest: Extract<Contest, { kind: "dribble" }>, sample: Sample, t: number, out: Map<string, Pose>): void {
  const progress = (t - contest.t) / DRIBBLE_S;
  if (progress < 0 || progress >= 1) return;
  const carrier = place(sample, contest.playerId);
  if (carrier === null) return;
  // A feint: out to one side and back, the way the take-on goes (side set by the carrier's place).
  const side = contest.playerId.length % 2 === 0 ? 1 : -1;
  const sway = Math.sin(2 * Math.PI * progress) * DODGE_PX * (contest.outcome === "success" ? 1 : 0.5);
  out.set(contest.playerId, { name: "stand", dx: 0, dy: sway * side, facing: 1 });
}

/** The poses of the players in a contest at `t`; everyone else just stands or runs. */
export function posesAt(contests: readonly Contest[], sample: Sample | null, t: number): Map<string, Pose> {
  const out = new Map<string, Pose>();
  if (sample === null) return out;
  for (let index = contests.length - 1; index >= 0; index--) {
    const contest = contests[index];
    if (contest === undefined) continue;
    if (t - contest.t > FALL_S) break;
    if (contest.t > t) continue;
    if (contest.kind === "tackle") tackle(contest, sample, t, out);
    else dribble(contest, sample, t, out);
  }
  return out;
}
