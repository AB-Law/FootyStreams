import type { FramePlayer, MatchClock } from "./events.ts";
import { FRAME_INTERVAL_S, type Frame } from "./store.ts";

/** A move larger than this between two frames is a reset (kick-off, half-time swap), not a run. */
const MAX_PLAYER_STEP = 0.2;
const MAX_BALL_STEP = 0.4;
/** Above this speed (m/s) a player is drawn mid-stride. */
const RUNNING_SPEED_MPS = 1.5;

export interface SamplePlayer {
  id: string;
  x: number;
  y: number;
  running: boolean;
}

export interface Sample {
  clock: MatchClock;
  scoreHome: number;
  scoreAway: number;
  ballX: number;
  ballY: number;
  carrierId: string | null;
  players: SamplePlayer[];
}

function lerp(from: number, to: number, alpha: number): number {
  return from + (to - from) * alpha;
}

function blend(from: FramePlayer, to: FramePlayer | undefined, alpha: number): SamplePlayer {
  const running = from.speed_mps > RUNNING_SPEED_MPS;
  if (to === undefined || Math.hypot(to.x - from.x, to.y - from.y) > MAX_PLAYER_STEP) {
    return { id: from.player_id, x: from.x, y: from.y, running };
  }
  return { id: from.player_id, x: lerp(from.x, to.x, alpha), y: lerp(from.y, to.y, alpha), running };
}

/**
 * The picture at time `t` seconds: positions blended between the two frames around `t`.
 *
 * Never extrapolates: past the last frame it holds the last frame. A player missing from the next
 * frame (substituted) or a jump too large to be running holds its position until the next frame.
 */
export function sampleAt(frames: readonly Frame[], t: number): Sample | null {
  if (frames.length === 0) return null;
  const position = Math.max(t, 0) / FRAME_INTERVAL_S;
  const index = Math.min(Math.floor(position), frames.length - 1);
  const from = frames[index];
  const to = frames[index + 1];
  if (from === undefined) return null;
  const alpha = to === undefined ? 0 : position - index;
  const next = new Map((to?.players ?? []).map((player) => [player.player_id, player]));
  const ballJumped = to !== undefined && Math.hypot(to.ballX - from.ballX, to.ballY - from.ballY) > MAX_BALL_STEP;
  const ballTo = to === undefined || ballJumped ? from : to;
  return {
    clock: from.clock,
    scoreHome: from.scoreHome,
    scoreAway: from.scoreAway,
    ballX: lerp(from.ballX, ballTo.ballX, alpha),
    ballY: lerp(from.ballY, ballTo.ballY, alpha),
    carrierId: from.carrierId,
    players: from.players.map((player) => blend(player, next.get(player.player_id), alpha)),
  };
}
