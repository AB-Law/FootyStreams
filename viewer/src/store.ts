import type { AnyEvent, BroadcastEvent, FrameEvent, FramePlayer, MatchClock, Pos, Side } from "./events.ts";
import { shotFlight, type Flight } from "./flights.ts";

/** Tracking frames are one sim second apart; a frame's index is its time in seconds. */
export const FRAME_INTERVAL_S = 1;

export interface Frame {
  clock: MatchClock;
  scoreHome: number;
  scoreAway: number;
  ballX: number;
  ballY: number;
  carrierId: string | null;
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

  /** The single entry point for events. Unknown types are ignored, never an error. */
  onEvent(event: AnyEvent): void {
    const known = event as BroadcastEvent;
    const t = this.duration;
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
      scoreHome: event.ctx.score_home,
      scoreAway: event.ctx.score_away,
      ballX: event.ball_pos_x,
      ballY: event.ball_pos_y,
      carrierId: event.carrier_id ?? null,
      players: event.players,
    });
  }
}

/** The end of the pitch (x = 0 or 1) a shot is at: the home side's direction is in the context. */
function attackedGoal(event: BroadcastEvent): 0 | 1 {
  const homeRight = event.ctx.attack_dir > 0;
  return homeRight === (event.team === "home") ? 1 : 0;
}
