import type { Pos } from "./events.ts";
import { teamOf, type ReplayMeta, type TeamSide } from "./meta.ts";
import type { Frame, LogEvent, MatchStore } from "./store.ts";

export interface Pair<T> {
  home: T;
  away: T;
}

export const PITCH_LENGTH_M = 105;
export const PITCH_WIDTH_M = 68;
/** A team has the ball in its attacking third beyond this share of the pitch (in its own frame). */
const THIRD = 2 / 3;
/** The pressing metric counts the opponents' passes in their own part of the pitch. */
const PRESS_ZONE = 0.6;
/** Momentum looks at this many seconds. */
export const MOMENTUM_WINDOW_S = 300;

export interface TeamStats {
  possession: number;
  fieldTilt: number;
  shots: number;
  onTarget: number;
  goals: number;
  xg: number;
  bigChances: number;
  passes: number;
  passesCompleted: number;
  progressivePasses: number;
  dribbles: number;
  dribblesWon: number;
  tackles: number;
  tacklesWon: number;
  interceptions: number;
  clearances: number;
  saves: number;
  fouls: number;
  offsides: number;
  corners: number;
  yellows: number;
  reds: number;
  ppda: number | null;
  distanceKm: number;
}

export interface PlayerTally {
  goals: number;
  assists: number;
  shots: number;
  onTarget: number;
  passes: number;
  passesCompleted: number;
  tacklesWon: number;
  interceptions: number;
  clearances: number;
  fouls: number;
  saves: number;
  dribblesWon: number;
  xg: number;
}

/** A point in the pitch as seen by `team`: x = 1 is the goal it attacks, whichever half it is. */
export function toTeamFrame(pos: Pos, team: TeamSide, homeDir: number): Pos {
  const attackingPositive = (team === "home") === homeDir > 0;
  return attackingPositive ? pos : { x: 1 - pos.x, y: 1 - pos.y };
}

export function metres(a: Pos, b: Pos): number {
  return Math.hypot((b.x - a.x) * PITCH_LENGTH_M, (b.y - a.y) * PITCH_WIDTH_M);
}

function other(side: TeamSide): TeamSide {
  return side === "home" ? "away" : "home";
}

function sideOf(team: string): TeamSide | null {
  return team === "home" || team === "away" ? team : null;
}

/** Index of the first element whose `t` is at least `time`. */
function lowerBound(events: readonly { t: number }[], time: number): number {
  let low = 0;
  let high = events.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if ((events[middle]?.t ?? 0) < time) low = middle + 1;
    else high = middle;
  }
  return low;
}

function emptyStats(): TeamStats {
  return {
    possession: 0,
    fieldTilt: 0,
    shots: 0,
    onTarget: 0,
    goals: 0,
    xg: 0,
    bigChances: 0,
    passes: 0,
    passesCompleted: 0,
    progressivePasses: 0,
    dribbles: 0,
    dribblesWon: 0,
    tackles: 0,
    tacklesWon: 0,
    interceptions: 0,
    clearances: 0,
    saves: 0,
    fouls: 0,
    offsides: 0,
    corners: 0,
    yellows: 0,
    reds: 0,
    ppda: null,
    distanceKm: 0,
  };
}

export function emptyTally(): PlayerTally {
  return { goals: 0, assists: 0, shots: 0, onTarget: 0, passes: 0, passesCompleted: 0, tacklesWon: 0, interceptions: 0, clearances: 0, fouls: 0, saves: 0, dribblesWon: 0, xg: 0 };
}

/** Running sums over the frames, so any window of the match is two lookups, not a scan. */
class FrameSums {
  readonly held: Pair<Float64Array>;
  readonly third: Pair<Float64Array>;
  readonly distance: Pair<Float64Array>;

  constructor(frames: readonly Frame[], meta: ReplayMeta) {
    const size = frames.length + 1;
    this.held = { home: new Float64Array(size), away: new Float64Array(size) };
    this.third = { home: new Float64Array(size), away: new Float64Array(size) };
    this.distance = { home: new Float64Array(size), away: new Float64Array(size) };
    let holder: TeamSide | null = null;
    frames.forEach((frame, index) => {
      holder = frame.carrierId === null ? holder : (teamOf(meta, frame.carrierId) ?? holder);
      for (const side of ["home", "away"] as const) {
        this.held[side][index + 1] = (this.held[side][index] ?? 0) + (holder === side ? 1 : 0);
        const ball = toTeamFrame({ x: frame.ballX, y: frame.ballY }, side, frame.homeDir);
        this.third[side][index + 1] = (this.third[side][index] ?? 0) + (ball.x > THIRD ? 1 : 0);
        this.distance[side][index + 1] = (this.distance[side][index] ?? 0) + sideDistance(frame, meta, side);
      }
    });
  }

  between(sums: Float64Array, from: number, to: number): number {
    const last = sums.length - 1;
    return (sums[Math.min(Math.max(Math.floor(to), 0), last)] ?? 0) - (sums[Math.min(Math.max(Math.floor(from), 0), last)] ?? 0);
  }
}

function sideDistance(frame: Frame, meta: ReplayMeta, side: TeamSide): number {
  let total = 0;
  for (const player of frame.players) if (teamOf(meta, player.player_id) === side) total += player.speed_mps;
  return total;
}

/** Statistics and tallies for any stretch of a replay, computed from the store and nothing else. */
export class StatsIndex {
  private readonly sums: FrameSums;
  private readonly store: MatchStore;

  constructor(store: MatchStore, meta: ReplayMeta) {
    this.store = store;
    this.sums = new FrameSums(store.frames, meta);
  }

  /** Both teams' statistics for the seconds `from` to `to` of the match. */
  teamStats(from: number, to: number): Pair<TeamStats> {
    const stats: Pair<TeamStats> = { home: emptyStats(), away: emptyStats() };
    const log = this.store.log;
    for (let index = lowerBound(log, from); index < log.length; index++) {
      const event = log[index];
      if (event === undefined || event.t > to) break;
      const side = sideOf(event.team);
      if (side !== null) countEvent(stats[side], event);
    }
    this.countCards(stats, from, to);
    this.countTerritory(stats, from, to);
    for (const side of ["home", "away"] as const) stats[side].ppda = this.pressingMetric(side, from, to);
    return stats;
  }

  private countCards(stats: Pair<TeamStats>, from: number, to: number): void {
    for (const mark of this.store.marks) {
      if (mark.kind !== "card" || mark.t < from || mark.t > to) continue;
      const side = sideOf(mark.team);
      if (side === null) continue;
      if (mark.colour === "yellow") stats[side].yellows++;
      else stats[side].reds++;
    }
  }

  private countTerritory(stats: Pair<TeamStats>, from: number, to: number): void {
    const held = { home: this.sums.between(this.sums.held.home, from, to), away: this.sums.between(this.sums.held.away, from, to) };
    const third = { home: this.sums.between(this.sums.third.home, from, to), away: this.sums.between(this.sums.third.away, from, to) };
    for (const side of ["home", "away"] as const) {
      stats[side].possession = share(held[side], held[other(side)]);
      stats[side].fieldTilt = share(third[side], third[other(side)]);
      stats[side].distanceKm = this.sums.between(this.sums.distance[side], from, to) / 1000;
    }
  }

  /** Opponent passes in their own part of the pitch per defensive action of ours in ours. */
  private pressingMetric(side: TeamSide, from: number, to: number): number | null {
    let passes = 0;
    let actions = 0;
    const log = this.store.log;
    for (let index = lowerBound(log, from); index < log.length; index++) {
      const event = log[index];
      if (event === undefined || event.t > to || event.pos === null) continue;
      const team = sideOf(event.team);
      if (team === null) continue;
      const seen = toTeamFrame(event.pos, team, event.homeDir);
      if (event.type === "pass" && team === other(side) && seen.x < PRESS_ZONE) passes++;
      const defensive = event.type === "tackle" || event.type === "interception" || event.type === "foul";
      if (defensive && team === side && seen.x > 1 - PRESS_ZONE) actions++;
    }
    return actions === 0 ? null : passes / actions;
  }

  /** Each player's tally from kick-off to `to` (or over a window when `from` is given). */
  playerTallies(to: number, from = 0): Map<string, PlayerTally> {
    const tallies = new Map<string, PlayerTally>();
    const get = (id: string | null): PlayerTally | null => {
      if (id === null) return null;
      let tally = tallies.get(id);
      if (tally === undefined) {
        tally = emptyTally();
        tallies.set(id, tally);
      }
      return tally;
    };
    const log = this.store.log;
    for (let index = lowerBound(log, from); index < log.length; index++) {
      const event = log[index];
      if (event === undefined || event.t > to) break;
      tallyEvent(event, get);
    }
    return tallies;
  }
}

function share(mine: number, theirs: number): number {
  const total = mine + theirs;
  return total === 0 ? 0.5 : mine / total;
}

function countEvent(stats: TeamStats, event: LogEvent): void {
  switch (event.type) {
    case "pass":
      stats.passes++;
      if (event.outcome === "complete") stats.passesCompleted++;
      if (event.progressive) stats.progressivePasses++;
      break;
    case "shot":
      stats.shots++;
      stats.xg += event.xg;
      if (event.outcome === "goal" || event.outcome === "saved") stats.onTarget++;
      if (event.xg >= BIG_CHANCE_XG) stats.bigChances++;
      break;
    case "goal":
      stats.goals++;
      break;
    case "tackle":
      stats.tackles++;
      if (event.outcome === "won") stats.tacklesWon++;
      break;
    case "dribble":
      stats.dribbles++;
      if (event.outcome === "success") stats.dribblesWon++;
      break;
    case "interception":
      stats.interceptions++;
      break;
    case "clearance":
      stats.clearances++;
      break;
    case "save":
      stats.saves++;
      break;
    case "foul":
      stats.fouls++;
      break;
    case "offside":
      stats.offsides++;
      break;
    case "corner":
      stats.corners++;
      break;
  }
}

/** A chance this good counts as a big one when the log carries only the xG. */
const BIG_CHANCE_XG = 0.3;

function tallyEvent(event: LogEvent, get: (id: string | null) => PlayerTally | null): void {
  const player = get(event.playerId);
  if (player === null) return;
  switch (event.type) {
    case "pass":
      player.passes++;
      if (event.outcome === "complete") player.passesCompleted++;
      break;
    case "shot":
      player.shots++;
      player.xg += event.xg;
      if (event.outcome === "goal" || event.outcome === "saved") player.onTarget++;
      break;
    case "goal":
      player.goals++;
      if (get(event.targetId) !== null) (get(event.targetId) as PlayerTally).assists++;
      break;
    case "tackle":
      if (event.outcome === "won") player.tacklesWon++;
      break;
    case "interception":
      player.interceptions++;
      break;
    case "clearance":
      player.clearances++;
      break;
    case "foul":
      player.fouls++;
      break;
    case "save":
      player.saves++;
      break;
    case "dribble":
      if (event.outcome === "success") player.dribblesWon++;
      break;
    default:
      break;
  }
}

/** A running form figure for the lineup: a viewer estimate, not a simulation output. */
export function formRating(tally: PlayerTally | undefined): number {
  if (tally === undefined) return 6;
  const raw =
    6 +
    0.9 * tally.goals +
    0.6 * tally.assists +
    0.02 * tally.passesCompleted -
    0.04 * (tally.passes - tally.passesCompleted) +
    0.2 * tally.tacklesWon +
    0.2 * tally.interceptions +
    0.15 * tally.saves +
    0.15 * tally.dribblesWon +
    0.1 * tally.onTarget -
    0.2 * tally.fouls;
  return Math.min(10, Math.max(3, raw));
}
