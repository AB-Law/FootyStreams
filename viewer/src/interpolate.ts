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
  /** Height of the ball above the grass in screen pixels (a pass in the air). */
  ballHeight: number;
  carrierId: string | null;
  players: SamplePlayer[];
}

/** A change of carrier is a pass: the ball covers the gap in this share of the second, then follows. */
const PASS_SHARE = 0.85;
/** Passes longer than this many metres (frame units are converted) leave the ground. */
const LOFT_FROM_M = 16;
const LOFT_SPAN_M = 40;
const MAX_LIFT_PX = 10;
const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;

/** Players keep at least this far apart (metres), a little over a body, so the large sprites do not stack on each other. */
const MIN_GAP_M = 3.2;

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

interface BallPlace {
  x: number;
  y: number;
  height: number;
}

/**
 * The ball follows the player who has it; when the carrier changes within the second it travels
 * from the old carrier to the new one (both still moving), so it never leaves the players.
 * Without a carrier on both ends it falls back to the frame's own ball.
 */
function ballPlace(from: Frame, to: Frame | undefined, alpha: number, players: SamplePlayer[]): BallPlace {
  const reset = to !== undefined && Math.hypot(to.ballX - from.ballX, to.ballY - from.ballY) > MAX_BALL_STEP;
  const end = to === undefined || reset ? from : to;
  const fallback = { x: lerp(from.ballX, end.ballX, alpha), y: lerp(from.ballY, end.ballY, alpha), height: 0 };
  // A frame with nobody on the ball is the ball in flight (or loose): the frame's own ball is the
  // truth, so follow it rather than gluing the ball to the last holder until the next frame.
  if (from.carrierId === null || (to !== undefined && to.carrierId === null)) return fallback;
  const holder = players.find((player) => player.id === from.carrierId);
  if (holder === undefined) return fallback;
  const receiver = to === undefined || to.carrierId === from.carrierId ? undefined : players.find((player) => player.id === to.carrierId);
  if (receiver === undefined) return { x: holder.x, y: holder.y, height: 0 };
  const share = Math.min(alpha / PASS_SHARE, 1);
  const travelled = share; // a ball in the air does not ease in and out
  const metres = Math.hypot((receiver.x - holder.x) * PITCH_LENGTH_M, (receiver.y - holder.y) * PITCH_WIDTH_M);
  const loft = Math.min(Math.max((metres - LOFT_FROM_M) / LOFT_SPAN_M, 0), 1) * MAX_LIFT_PX;
  return {
    x: lerp(holder.x, receiver.x, travelled),
    y: lerp(holder.y, receiver.y, travelled),
    height: loft * 4 * share * (1 - share),
  };
}

/**
 * Push apart players who are closer than a body width, half each way. Every shift is worked out
 * from the positions before any move, so the result does not depend on the order of the list.
 */
export function separate(players: readonly SamplePlayer[]): SamplePlayer[] {
  const shift = players.map(() => ({ x: 0, y: 0 }));
  for (let first = 0; first < players.length; first++) {
    for (let second = first + 1; second < players.length; second++) {
      const a = players[first];
      const b = players[second];
      const pushA = shift[first];
      const pushB = shift[second];
      if (a === undefined || b === undefined || pushA === undefined || pushB === undefined) continue;
      const dx = (b.x - a.x) * PITCH_LENGTH_M;
      const dy = (b.y - a.y) * PITCH_WIDTH_M;
      const gap = Math.hypot(dx, dy);
      if (gap >= MIN_GAP_M) continue;
      // Players on exactly the same spot are split along the pitch; the list order is stable.
      const along = gap === 0 ? { x: 1, y: 0 } : { x: dx / gap, y: dy / gap };
      const half = (MIN_GAP_M - gap) / 2;
      pushA.x -= (along.x * half) / PITCH_LENGTH_M;
      pushA.y -= (along.y * half) / PITCH_WIDTH_M;
      pushB.x += (along.x * half) / PITCH_LENGTH_M;
      pushB.y += (along.y * half) / PITCH_WIDTH_M;
    }
  }
  return players.map((player, index) => ({ ...player, x: player.x + (shift[index]?.x ?? 0), y: player.y + (shift[index]?.y ?? 0) }));
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
  const players = separate(from.players.map((player) => blend(player, next.get(player.player_id), alpha)));
  const ball = ballPlace(from, to, alpha, players);
  return {
    clock: from.clock,
    scoreHome: from.scoreHome,
    scoreAway: from.scoreAway,
    ballX: ball.x,
    ballY: ball.y,
    ballHeight: ball.height,
    carrierId: from.carrierId,
    players,
  };
}
