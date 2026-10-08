import type { Frame } from "./store.ts";

/** The ball moving less than this many metres in a second counts as standing still. */
const STILL_METRES = 0.3;
/** A stoppage shorter than this is left alone (a quick throw is part of the play). */
const MIN_STOPPAGE_S = 4;
/** The first moments of a stoppage still play at normal speed, so the cause is seen. */
const LEAD_IN_S = 1.5;
const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;

export interface Span {
  start: number;
  end: number;
}

/** Stretches of time where the ball is dead (throw-in, goal kick, injury, celebration). */
export function deadSpans(frames: readonly Frame[]): Span[] {
  const spans: Span[] = [];
  let runStart = 0;
  for (let index = 1; index <= frames.length; index++) {
    const before = frames[index - 1];
    const now = frames[index];
    const still =
      before !== undefined &&
      now !== undefined &&
      Math.hypot((now.ballX - before.ballX) * PITCH_LENGTH_M, (now.ballY - before.ballY) * PITCH_WIDTH_M) < STILL_METRES;
    if (still) continue;
    if (index - 1 - runStart >= MIN_STOPPAGE_S) spans.push({ start: runStart + LEAD_IN_S, end: index - 1 });
    runStart = index;
  }
  return spans;
}

/** True when `t` lies inside one of the (time-ordered) spans. */
export function isDead(spans: readonly Span[], t: number): boolean {
  let low = 0;
  let high = spans.length - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    const span = spans[middle];
    if (span === undefined) return false;
    if (t < span.start) high = middle - 1;
    else if (t >= span.end) low = middle + 1;
    else return true;
  }
  return false;
}
