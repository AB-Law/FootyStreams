import type { Pos } from "./events.ts";
import type { Frame, Mark } from "./store.ts";
import { FRAME_INTERVAL_S } from "./store.ts";

/** The referee trails the play: he stands where the ball has been over the last few seconds. */
const FOLLOW_SECONDS = 5;
const FOLLOW_SAMPLES = 6;
/** He keeps off the line of play, on the side of the pitch away from the ball (fraction of width). */
const SIDE_STEP = 0.14;
/** And stays a little behind it towards the centre circle (fraction of length). */
const CENTRE_PULL = 0.15;
/** Beside an incident, in the same units as positions. */
const INCIDENT_GAP = { x: 0.015, y: 0.04 };

function ballAt(frames: readonly Frame[], t: number): Pos {
  const position = Math.max(t, 0) / FRAME_INTERVAL_S;
  const index = Math.min(Math.floor(position), frames.length - 1);
  const from = frames[index];
  const to = frames[index + 1];
  if (from === undefined) return { x: 0.5, y: 0.5 };
  const alpha = to === undefined ? 0 : position - index;
  return {
    x: from.ballX + ((to?.ballX ?? from.ballX) - from.ballX) * alpha,
    y: from.ballY + ((to?.ballY ?? from.ballY) - from.ballY) * alpha,
  };
}

/** Where the referee stands at `t`: behind the play, off its line, moving smoothly with it. */
export function refereeAt(frames: readonly Frame[], t: number): Pos {
  let x = 0;
  let y = 0;
  for (let step = 0; step < FOLLOW_SAMPLES; step++) {
    const ball = ballAt(frames, t - (step * FOLLOW_SECONDS) / (FOLLOW_SAMPLES - 1));
    x += ball.x / FOLLOW_SAMPLES;
    y += ball.y / FOLLOW_SAMPLES;
  }
  const side = y < 0.5 ? 1 : -1;
  return {
    x: Math.min(Math.max(x + (0.5 - x) * CENTRE_PULL, 0.04), 0.96),
    y: Math.min(Math.max(y + side * SIDE_STEP, 0.08), 0.92),
  };
}

/** Beside a foul or a booking, on the side nearer the centre of the pitch. */
export function atIncident(spot: Pos): Pos {
  return {
    x: spot.x + (spot.x < 0.5 ? INCIDENT_GAP.x : -INCIDENT_GAP.x),
    y: spot.y + (spot.y < 0.5 ? INCIDENT_GAP.y : -INCIDENT_GAP.y),
  };
}

/** A referee runs at most this fast (metres per second), so he can never jump across the pitch. */
const MAX_SPEED_MPS = 6.5;
/** The chase is replayed from this many seconds back, which is plenty to catch up from anywhere. */
const LOOKBACK_S = 45;
/** He stays by a foul or a booking this long (match seconds, whatever the playback speed). */
const INCIDENT_HOLD_S = 6;
const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;

export interface RefereeView {
  spot: Pos;
  /** True while he is at a foul or a booking with the whistle in his mouth. */
  incident: boolean;
}

function incidentSpot(frames: readonly Frame[], marks: readonly Mark[], t: number): Pos | null {
  for (let index = marks.length - 1; index >= 0; index--) {
    const mark = marks[index];
    if (mark === undefined || mark.t > t) continue;
    if (t - mark.t > INCIDENT_HOLD_S) return null;
    if (mark.kind === "foul" && mark.pos !== null) return mark.pos;
    if (mark.kind === "card") {
      const frame = frames[Math.min(Math.floor(mark.t / FRAME_INTERVAL_S), frames.length - 1)];
      const player = frame?.players.find((candidate) => candidate.player_id === mark.playerId);
      if (player !== undefined) return { x: player.x, y: player.y };
    }
  }
  return null;
}

function targetAt(frames: readonly Frame[], marks: readonly Mark[], t: number): { spot: Pos; incident: boolean } {
  const spot = incidentSpot(frames, marks, t);
  return spot === null ? { spot: refereeAt(frames, t), incident: false } : { spot: atIncident(spot), incident: true };
}

function stepToward(from: Pos, to: Pos, seconds: number): Pos {
  const dx = (to.x - from.x) * PITCH_LENGTH_M;
  const dy = (to.y - from.y) * PITCH_WIDTH_M;
  const distance = Math.hypot(dx, dy);
  const reach = MAX_SPEED_MPS * seconds;
  if (distance <= reach) return to;
  const share = reach / distance;
  return { x: from.x + (to.x - from.x) * share, y: from.y + (to.y - from.y) * share };
}

/**
 * Where the referee is at `t`: he chases a target (behind the play, or beside a foul or booking)
 * at running speed. The chase is replayed from a few seconds back, so the result depends only on
 * `t`: scrubbing and every playback speed show the same, smooth path.
 */
export function refereeTrack(frames: readonly Frame[], marks: readonly Mark[], t: number): RefereeView | null {
  if (frames.length === 0) return null;
  // Whole seconds only: the grid must not shift with `t`, or two nearby times would disagree.
  let moment = Math.max(Math.floor(t / FRAME_INTERVAL_S) * FRAME_INTERVAL_S - LOOKBACK_S, 0);
  let spot = targetAt(frames, marks, moment).spot;
  while (moment < t) {
    const next = Math.min(moment + FRAME_INTERVAL_S, t);
    // The aim is fixed for the whole second, so a partial step and a full one lie on one path.
    spot = stepToward(spot, targetAt(frames, marks, moment).spot, next - moment);
    moment = next;
  }
  return { spot, incident: targetAt(frames, marks, t).incident };
}
