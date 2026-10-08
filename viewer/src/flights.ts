import type { PassEvent, Pos, ShotEvent } from "./events.ts";

const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;
const PASS_SPEED_MPS = 17;
const SHOT_SPEED_MPS = 26;
const MIN_FLIGHT_S = 0.3;
/** Peak height of a ball in the air, in screen pixels, for a full loft. */
const MAX_LIFT_PX = 12;
/** Balls longer than this start to leave the ground; a cross-field ball is fully lofted at 55 m. */
const LOFT_FROM_M = 18;
const LOFT_SPAN_M = 37;
const DEFAULT_SHOT_LOFT = 0.15;
const MAX_QUEUE_DELAY_S = 0.9;
/** A curve of 1 bows the path sideways by a quarter of its length at the control point (an eighth on the ball). */
const MAX_BEND = 0.25;

/** A ball in the air between two points: straight, or bent by `bend` (fraction of its length). */
export interface Flight {
  t0: number;
  t1: number;
  from: Pos;
  to: Pos;
  bend: number;
  lift: number;
  fast: boolean;
}

export interface BallPoint {
  x: number;
  y: number;
  /** Height above the ground in screen pixels. */
  height: number;
  /** 0 at the kick, 1 on arrival. */
  progress: number;
}

function metres(from: Pos, to: Pos): { dx: number; dy: number; length: number } {
  const dx = (to.x - from.x) * PITCH_LENGTH_M;
  const dy = (to.y - from.y) * PITCH_WIDTH_M;
  return { dx, dy, length: Math.hypot(dx, dy) };
}

function duration(length: number, speed: number): number {
  return Math.max(length / speed, MIN_FLIGHT_S);
}

/** A pass flies at a steady speed and leaves the ground the longer it is. */
export function passFlight(event: PassEvent, start: number): Flight | null {
  if (event.pos === null || event.end_pos === null) return null;
  const { length } = metres(event.pos, event.end_pos);
  const loft = Math.min(Math.max((length - LOFT_FROM_M) / LOFT_SPAN_M, 0), 1);
  return { t0: start, t1: start + duration(length, PASS_SPEED_MPS), from: event.pos, to: event.end_pos, bend: 0, lift: loft * MAX_LIFT_PX, fast: false };
}

/**
 * A shot flies fast along the curve the sim gave it. Without a `target` (older logs) it goes
 * straight at the middle of the goal being attacked, `goalX` being 0 or 1.
 */
export function shotFlight(event: ShotEvent, start: number, goalX: 0 | 1): Flight | null {
  if (event.pos === null) return null;
  const to = event.target ?? { x: goalX, y: 0.5 };
  const { length } = metres(event.pos, to);
  const speed = event.speed_mps ?? SHOT_SPEED_MPS;
  const lift = (event.loft ?? DEFAULT_SHOT_LOFT) * MAX_LIFT_PX;
  return { t0: start, t1: start + duration(length, speed), from: event.pos, to, bend: (event.curve ?? 0) * MAX_BEND, lift, fast: true };
}

/** Start a flight at the later of its own time and the end of the previous one, but no later than a beat. */
export function startAfter(eventTime: number, previous: Flight | undefined): number {
  const free = previous === undefined ? eventTime : Math.max(eventTime, previous.t1);
  return Math.min(free, eventTime + MAX_QUEUE_DELAY_S);
}

/** The ball's place `t` seconds into the match on this flight (clamped to its ends). */
export function ballOnFlight(flight: Flight, t: number): BallPoint {
  const progress = Math.min(Math.max((t - flight.t0) / (flight.t1 - flight.t0), 0), 1);
  const { dx, dy } = metres(flight.from, flight.to);
  // The control point sits beside the middle of the line, so the path bows towards one side.
  const controlX = dx / 2 - dy * flight.bend;
  const controlY = dy / 2 + dx * flight.bend;
  const along = 1 - progress;
  const x = 2 * along * progress * controlX + progress * progress * dx;
  const y = 2 * along * progress * controlY + progress * progress * dy;
  return {
    x: flight.from.x + x / PITCH_LENGTH_M,
    y: flight.from.y + y / PITCH_WIDTH_M,
    height: flight.lift * 4 * progress * (1 - progress),
    progress,
  };
}

/** The flight carrying the ball at `t`, if any: the latest one that has started and not landed. */
export function activeFlight(flights: readonly Flight[], t: number): Flight | null {
  let low = 0;
  let high = flights.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if ((flights[middle]?.t0 ?? Infinity) <= t) low = middle + 1;
    else high = middle;
  }
  for (let index = low - 1; index >= Math.max(low - 3, 0); index--) {
    const flight = flights[index];
    if (flight !== undefined && t < flight.t1) return flight;
  }
  return null;
}
