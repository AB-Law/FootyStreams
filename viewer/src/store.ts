import type { AnyEvent, BroadcastEvent, FrameEvent, FramePlayer, MatchClock, Pos, Side } from "./events.ts";
import { shotFlight, type Flight } from "./flights.ts";
import { isSkillMove, type SkillMoveName } from "./skillposes.ts";

/** A contest worth animating: a tackle (won, missed or a foul) or a take-on. */
export type Contest =
  | { kind: "tackle"; t: number; tacklerId: string; targetId: string; outcome: "won" | "foul" | "missed" }
  | { kind: "dribble"; t: number; playerId: string; outcome: "success" | "tackled" | "lost"; move: SkillMoveName | null }
  | { kind: "restart"; t: number; restart: "throw_in" | "goal_kick" | "corner" | "free_kick" | "penalty"; takerId: string; team: Side };

/** Tracking frames are one sim second apart; a frame's index is its time in seconds. */
export const FRAME_INTERVAL_S = 1;

/**
 * Home's attacking direction (+1 toward x = 1) in a period. `ctx.attack_dir` on an event is the
 * direction of the side in possession, not home's, so the period is the reliable source.
 */
export function homeDirection(period: number): number {
  return period <= 1 ? 1 : -1;
}

/** An event that counts toward the statistics and maps, stamped like a mark (frame seconds). */
export interface LogEvent {
  t: number;
  type: "pass" | "shot" | "tackle" | "interception" | "clearance" | "foul" | "offside" | "corner" | "save" | "dribble" | "goal";
  team: Side;
  playerId: string | null;
  targetId: string | null;
  pos: Pos | null;
  endPos: Pos | null;
  outcome: string | null;
  xg: number;
  progressive: boolean;
  /** Home's attacking direction when it happened: +1 toward x = 1, -1 toward x = 0. */
  homeDir: number;
}

export interface Frame {
  clock: MatchClock;
  /** Home's attacking direction (+1 toward x = 1); the sides swap at half-time. */
  homeDir: number;
  scoreHome: number;
  scoreAway: number;
  ballX: number;
  ballY: number;
  carrierId: string | null;
  /** Metres above the grass, or null for a replay recorded before frames carried it. */
  ballHeightM: number | null;
  players: FramePlayer[];
}

export type CardColour = "yellow" | "red" | "second_yellow";

/** A moment worth an overlay, stamped with the time of the latest frame seen when it arrived. */
export type Mark =
  | { kind: "goal"; t: number; team: Side; scorerId: string; ownGoal: boolean; scoreHome: number; scoreAway: number; minute: number }
  | { kind: "card"; t: number; team: Side; playerId: string; colour: CardColour }
  | { kind: "substitution"; t: number; team: Side; offId: string; onId: string }
  | { kind: "foul"; t: number; team: Side; pos: Pos | null }
  | { kind: "halftime"; t: number; scoreHome: number; scoreAway: number }
  | { kind: "fulltime"; t: number; scoreHome: number; scoreAway: number };

/**
 * Everything the screen needs, built only by `onEvent`.
 *
 * A live source calls `onEvent` as events arrive; the file reader calls it for every line. The
 * store only appends, so the picture at any time is a pure function of it (scrubbing is free).
 */
export class MatchStore {
  readonly frames: Frame[] = [];
  readonly marks: Mark[] = [];
  readonly flights: Flight[] = [];
  readonly contests: Contest[] = [];
  readonly log: LogEvent[] = [];

  /** The single entry point for events. Unknown types are ignored, never an error. */
  onEvent(event: AnyEvent): void {
    const known = event as BroadcastEvent;
    const t = this.duration;
    const logged = logEvent(known, t);
    if (logged !== null) this.log.push(logged);
    switch (known.type) {
      case "frame":
        this.addFrame(known);
        break;
      case "goal":
        this.marks.push({ kind: "goal", t, team: known.team, scorerId: known.scorer_id, ownGoal: known.own_goal === true, scoreHome: known.ctx.score_home, scoreAway: known.ctx.score_away, minute: known.clock.minute });
        break;
      case "card":
        this.marks.push({ kind: "card", t, team: known.team, playerId: known.player_id, colour: known.colour });
        break;
      case "substitution":
        this.marks.push({ kind: "substitution", t, team: known.team, offId: known.player_off_id, onId: known.player_on_id });
        break;
      case "tackle":
        this.contests.push({ kind: "tackle", t, tacklerId: known.player_id, targetId: known.target_id, outcome: known.outcome });
        break;
      case "dribble":
        this.contests.push({ kind: "dribble", t, playerId: known.player_id, outcome: known.outcome, move: isSkillMove(known.skill_move) ? known.skill_move : null });
        break;
      case "throw_in":
      case "goal_kick":
      case "corner":
      case "free_kick":
      case "penalty":
        this.contests.push({ kind: "restart", t, restart: known.type, takerId: known.taker_id, team: known.team });
        break;
      case "foul":
        this.marks.push({ kind: "foul", t, team: known.team, pos: known.pos });
        break;
      case "shot":
        this.addFlight(shotFlight(known, t, attackedGoal(known)));
        break;
      case "halftime":
      case "fulltime":
        this.marks.push({ kind: known.type, t, scoreHome: known.ctx.score_home, scoreAway: known.ctx.score_away });
        break;
      default:
        break; // pass, tackle, review, ... not drawn as such (the carrier changing is the pass)
    }
  }

  private addFlight(flight: Flight | null): void {
    if (flight !== null) this.flights.push(flight);
  }

  /** Seconds of match covered so far. */
  get duration(): number {
    return Math.max(this.frames.length - 1, 0) * FRAME_INTERVAL_S;
  }

  private addFrame(event: FrameEvent): void {
    if (!Array.isArray(event.players)) return;
    this.frames.push({
      clock: event.clock,
      homeDir: homeDirection(event.clock.period),
      scoreHome: event.ctx.score_home,
      scoreAway: event.ctx.score_away,
      ballX: event.ball_pos_x,
      ballY: event.ball_pos_y,
      carrierId: event.carrier_id ?? null,
      ballHeightM: typeof event.ball_height_m === "number" ? event.ball_height_m : null,
      players: event.players,
    });
  }
}

/** The end of the pitch (x = 0 or 1) a shot is at, from the period and the shooting side. */
function attackedGoal(event: BroadcastEvent): 0 | 1 {
  const homeRight = homeDirection(event.clock.period) > 0;
  return homeRight === (event.team === "home") ? 1 : 0;
}

const LOGGED: Record<string, LogEvent["type"]> = {
  pass: "pass",
  shot: "shot",
  tackle: "tackle",
  interception: "interception",
  clearance: "clearance",
  foul: "foul",
  offside: "offside",
  corner: "corner",
  save: "save",
  dribble: "dribble",
  goal: "goal",
};

/** The statistics view of an event: who did it, to whom, where, and how it turned out. */
function logEvent(event: BroadcastEvent, t: number): LogEvent | null {
  const type = LOGGED[event.type];
  if (type === undefined) return null;
  const fields = event as unknown as Record<string, unknown>;
  const text = (name: string): string | null => (typeof fields[name] === "string" ? (fields[name] as string) : null);
  return {
    t,
    type,
    team: event.team,
    playerId: text("player_id") ?? text("from_player_id") ?? text("fouler_id") ?? text("taker_id") ?? text("keeper_id") ?? text("scorer_id"),
    targetId: text("to_player_id") ?? text("target_id") ?? text("assist_id"),
    pos: event.pos,
    endPos: (fields["end_pos"] as Pos | null | undefined) ?? null,
    outcome: text("outcome"),
    xg: typeof fields["xg"] === "number" ? fields["xg"] : 0,
    progressive: fields["progressive"] === true,
    homeDir: homeDirection(event.clock.period),
  };
}
