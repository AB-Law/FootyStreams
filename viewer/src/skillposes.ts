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
}

const SMOOTH = (progress: number): number => progress * progress * (3 - 2 * progress);
const HUMP = (progress: number): number => Math.sin(Math.PI * Math.min(Math.max(progress, 0), 1));

const NONE: SkillFrame = { along: 0, across: 0, ballAlong: 0, ballAcross: 0, ballLift: 0 };

/** Every offset eases to nothing over the last part of a move, so nothing snaps back when it ends. */
const FADE_FROM = 0.7;

function faded(frame: SkillFrame, progress: number): SkillFrame {
  const keep = 1 - SMOOTH(Math.min(Math.max((progress - FADE_FROM) / (1 - FADE_FROM), 0), 1));
  return {
    ...frame,
    along: frame.along * keep,
    across: frame.across * keep,
    ballAlong: frame.ballAlong * keep,
    ballAcross: frame.ballAcross * keep,
    ballLift: frame.ballLift * keep,
  };
}

/**
 * The shape of each skill move over `progress` from 0 to 1, in the pixels of the top-down view
 * (about 2.9 to the metre). The real positions in the frames already carry the player and the ball
 * on, so a move only adds a flourish that starts and ends at nothing: the body shifts by a metre at
 * most (he must not walk through the defender) and the ball by up to three.
 */
export function skillFrame(move: SkillMoveName, progress: number): SkillFrame {
  const p = Math.min(Math.max(progress, 0), 1);
  return faded(shape(move, p), p);
}

function shape(move: SkillMoveName, p: number): SkillFrame {
  switch (move) {
    case "knock_past":
      // The ball is pushed a little ahead and he strides on to it.
      return { ...NONE, ballAlong: 8 * HUMP(Math.min(p / 0.8, 1)), along: 2 * HUMP(p) };
    case "step_over":
      // A foot swung over the ball one way, then a push off the other.
      return { ...NONE, across: 2.5 * Math.sin(Math.PI * 2 * p), along: 1.5 * HUMP(p) };
    case "drag_back":
      // The ball is pulled back under the sole, then he turns away with it.
      return { ...NONE, ballAlong: -6 * HUMP(Math.min(p / 0.6, 1)), along: -1.5 * HUMP(p) };
    case "cut_inside":
      // He drops a shoulder and takes the ball across his body toward the middle.
      return { ...NONE, across: 2.5 * HUMP(p), ballAcross: 8 * HUMP(Math.min(p / 0.7, 1)), along: 2 * HUMP(p) };
    case "nutmeg":
      // The ball goes through the defender's legs and he steps round to collect it.
      return { ...NONE, ballAlong: 9 * HUMP(Math.min(p / 0.8, 1)), across: 1.5 * HUMP(p) };
    case "roulette":
      // A full turn over the ball, the ball dragged round in a small circle.
      return {
        ...NONE,
        ballAlong: 3 * Math.sin(2 * Math.PI * p),
        ballAcross: 3 * (1 - Math.cos(2 * Math.PI * p)),
        along: 1.5 * HUMP(p),
      };
    case "rainbow_flick":
      // The ball flicked up and over his own head and the defender's.
      return { ...NONE, ballAlong: 10 * HUMP(Math.min(p / 0.9, 1)), ballLift: 16 * HUMP(Math.min(p / 0.9, 1)), along: 2 * HUMP(p) };
  }
}

export function isSkillMove(value: unknown): value is SkillMoveName {
  return typeof value === "string" && (SKILL_MOVES as readonly string[]).includes(value);
}
