import type { ProfilePose } from "./profile.ts";

/** The skill moves the sim records on a dribble (src/footystreams/events/open_play.py). */
export type SkillMoveName = "knock_past" | "step_over" | "drag_back" | "cut_inside" | "nutmeg" | "roulette" | "rainbow_flick";

export const SKILL_MOVES: readonly SkillMoveName[] = ["knock_past", "step_over", "drag_back", "cut_inside", "nutmeg", "roulette", "rainbow_flick"];

/** How long a skill move plays, in match seconds: longer than a plain take-on so it can be read. */
export const SKILL_MOVE_S = 1.6;

/** What a skill move does to the player and the ball at one moment of it. */
export interface SkillFrame {
  /** The player shifts along his running direction by this many pixels (top-down scale) ... */
  along: number;
  /** ... and across it (positive toward the middle of the pitch). */
  across: number;
  /** The ball is this far ahead of where it would be, and this far to the side. */
  ballAlong: number;
  ballAcross: number;
  /** The ball lifts off the grass by this many pixels. */
  ballLift: number;
  profile: ProfilePose;
  /** +1 keeps facing the way he runs, -1 has him turned round (the middle of a roulette). */
  turn: 1 | -1;
}

const SMOOTH = (progress: number): number => progress * progress * (3 - 2 * progress);
const HUMP = (progress: number): number => Math.sin(Math.PI * Math.min(Math.max(progress, 0), 1));

function plain(profile: ProfilePose): SkillFrame {
  return { along: 0, across: 0, ballAlong: 0, ballAcross: 0, ballLift: 0, profile, turn: 1 };
}

/**
 * The shape of each skill move over `progress` from 0 to 1, in the pixels of the top-down view
 * (about 2.9 to the metre). They are drawn from the sim's choice alone: the outcome decides whether
 * the defender then gets the ball, which the contest code shows separately.
 */
export function skillFrame(move: SkillMoveName, progress: number): SkillFrame {
  const p = Math.min(Math.max(progress, 0), 1);
  switch (move) {
    case "knock_past":
      // The ball is pushed well ahead and he sprints on to it.
      return { ...plain("lean"), ballAlong: 14 * SMOOTH(Math.min(p / 0.5, 1)), along: 10 * SMOOTH(Math.max((p - 0.3) / 0.7, 0)) };
    case "step_over":
      // A foot swung over the ball one way, then a push off the other.
      return { ...plain(p < 0.45 ? "feint" : "stepA"), across: 5 * Math.sin(Math.PI * 2 * p) * (p < 0.7 ? 1 : 0.3), along: 4 * SMOOTH(p) };
    case "drag_back":
      // The ball is pulled back under the sole, then he turns away with it.
      return { ...plain(p < 0.5 ? "kick" : "stepB"), ballAlong: -7 * HUMP(Math.min(p / 0.6, 1)), along: -2 * HUMP(p) };
    case "cut_inside":
      // He drops a shoulder and takes the ball across his body toward the middle.
      return { ...plain("lean"), across: 9 * SMOOTH(p), ballAcross: 11 * SMOOTH(Math.min(p / 0.6, 1)), along: 5 * p };
    case "nutmeg":
      // The ball goes through the defender's legs and he runs round to collect it.
      return { ...plain(p < 0.35 ? "kick" : "lean"), ballAlong: 16 * SMOOTH(Math.min(p / 0.45, 1)), along: 14 * SMOOTH(Math.max((p - 0.25) / 0.75, 0)) };
    case "roulette":
      // A full turn over the ball, the ball dragged round in a small circle.
      return {
        ...plain(p < 0.5 ? "stepA" : "stepB"),
        turn: p > 0.3 && p < 0.65 ? -1 : 1,
        ballAlong: 4 * Math.sin(2 * Math.PI * p),
        ballAcross: 4 * (1 - Math.cos(2 * Math.PI * p)),
        along: 6 * SMOOTH(p),
      };
    case "rainbow_flick":
      // The ball flicked up and over his own head and the defender's.
      return { ...plain("flick"), ballAlong: 20 * SMOOTH(Math.min(p / 0.8, 1)), ballLift: 16 * HUMP(Math.min(p / 0.9, 1)), along: 12 * SMOOTH(Math.max((p - 0.2) / 0.8, 0)) };
  }
}

export function isSkillMove(value: unknown): value is SkillMoveName {
  return typeof value === "string" && (SKILL_MOVES as readonly string[]).includes(value);
}
