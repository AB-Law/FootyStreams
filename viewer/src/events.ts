// Hand-written types for the broadcast events the viewer reads, and only those. Do not generate:
// the broadcast schema export is deferred to the next schema bump (docs/design/08-roadmap.md 3a).
//
// Python sources of truth:
//   EventBase, MatchClock, Participant ... src/footystreams/events/base.py
//   EventContext ......................... src/footystreams/events/context.py
//   FrameEvent, FramePlayer, Halftime/Fulltime ... src/footystreams/events/structure.py
//   GoalEvent ............................ src/footystreams/events/open_play.py
//   CardEvent, SubstitutionEvent ......... src/footystreams/events/discipline.py
//
// Pitch coordinates are absolute, 0..1: x along the length, y across the width. The home side
// defends x=0 in period 1 and the sides swap at half-time (ctx.attack_dir is home's direction).

export type Side = "home" | "away" | "none";

export interface MatchClock {
  period: number;
  minute: number;
  second: number;
  stoppage: number;
}

export interface EventContext {
  score_home: number;
  score_away: number;
  attack_dir: number;
}

export interface Participant {
  player_id: string;
  role: string;
}

export interface EventBase {
  type: string;
  team: Side;
  clock: MatchClock;
  ctx: EventContext;
  participants: Participant[];
}

export interface FramePlayer {
  player_id: string;
  x: number;
  y: number;
  speed_mps: number;
  exhaustion: number;
}

/** One tracking frame per sim second; `players` is home then away, in slot order. */
export interface FrameEvent extends EventBase {
  type: "frame";
  ball_pos_x: number;
  ball_pos_y: number;
  carrier_id: string | null;
  players: FramePlayer[];
}

export interface GoalEvent extends EventBase {
  type: "goal";
  scorer_id: string;
  assist_id: string | null;
  own_goal: boolean;
}

export interface CardEvent extends EventBase {
  type: "card";
  player_id: string;
  colour: "yellow" | "red" | "second_yellow";
}

export interface SubstitutionEvent extends EventBase {
  type: "substitution";
  player_off_id: string;
  player_on_id: string;
}

export interface HalftimeEvent extends EventBase {
  type: "halftime";
}

export interface FulltimeEvent extends EventBase {
  type: "fulltime";
}

/** Anything else the log may carry (pass, shot, review ...): accepted and ignored. */
export interface OtherEvent {
  type: string;
}

export type BroadcastEvent =
  | FrameEvent
  | GoalEvent
  | CardEvent
  | SubstitutionEvent
  | HalftimeEvent
  | FulltimeEvent;

export type AnyEvent = BroadcastEvent | OtherEvent;
