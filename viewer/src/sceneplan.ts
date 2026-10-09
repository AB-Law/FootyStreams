import { MOVE_SCRIPTS, defenderAt, type Foot, type Script } from "./choreo.ts";
import { sampleAt, type SamplePlayer } from "./interpolate.ts";
import { teamOf, type ReplayMeta } from "./meta.ts";
import { kickTime } from "./poses.ts";
import { HEADER_CONTACT_S, KICK_TOUCH_S, MOVE_CHALLENGE_AT, defenderSide, failedMove, headerScript, kickScript, tackleScript, withLeadIn, type Approach, type ChallengeMode } from "./scenes.ts";
import type { Contest, Frame, MatchStore } from "./store.ts";

// Plans the scenes in choreo.ts and scenes.ts over a replay. Each dribble, tackle, header and dead-ball
// kick in the log becomes a plan: which script, started when, on which players, from which side the
// defender comes and with which foot. A plan is built from where the replay really has the players, so
// a scene is never asked to do what the replay makes impossible (see `ScenePlanner.duel`).

export const PITCH_LENGTH_M = 105;
export const PITCH_WIDTH_M = 68;
/** The longest a scene can stretch before its contact (a lost ball is found in the frames within this). */
export const SEARCH_S = 12;
/** A challenge is a slide this often, decided by the players and the moment so it never changes on a replay. */
const SLIDE_SHARE = 0.3;
const WEAK_FOOT_SHARE = 0.25;
const WALL_MIN_M = 6;
const WALL_MAX_M = 12;
const WALL_SIZE = 4;
const WALL_ANGLE = 0.45;
/** A defender farther than this from the carrier when the scene's contact comes is not part of it. */
const REACH_MAX_M = 7;
/** He is brought in from behind rather than from the front when he is more than this far behind. */
const BEHIND_FROM_M = 0.8;
/** How fast, in metres a second and on top of how the replay moves him, a defender is asked to close in. */
const CLOSE_PACE_MPS = 3.5;
const MAX_LEAD_S = 2;
/** Closer than this to the line of the run and the defender stays on the side the script put him. */
const SIDE_DEADBAND_M = 0.4;

export interface Vec {
  x: number;
  y: number;
}

/** Where one player is from another, along the run (`f`) and toward the middle of the pitch (`l`), in metres. */
interface Relation {
  f: number;
  l: number;
  distance: number;
}

interface RunFrame {
  forward: Vec;
  inward: Vec;
}

/** How a duel is put together (see `ScenePlanner.duel`). */
interface Duel {
  /** A challenge cannot be played without the man who makes it. */
  needsDefender: boolean;
  /** The script for a defender coming from the front (1) or from behind (-1); null when it has no such version. */
  build: (approach: Approach) => Script | null;
  /** When the scene starts, given the script (seconds of replay). */
  start: (script: Script) => number;
  /** How long after its start the ball changes hands or the carrier is caught. */
  contact: (script: Script) => number;
  /** The way the carrier faces where the replay's own run does not say. */
  forward?: Vec;
  /** False when the scene never has the defender come from behind. */
  fromBehind?: boolean;
}

export interface Plan {
  start: number;
  /** Seconds of script per second of replay (above 1 plays a kick faster when there is little time). */
  scale: number;
  script: Script;
  attacker: string;
  defender: string | null;
  wall: string[];
  forward: Vec;
  inward: Vec;
  foot: Foot;
  /** Which side of the carrier the defender keeps to: 1 inside, -1 outside. */
  side: 1 | -1;
  /** Seconds into the script that the ball changes hands or the carrier is caught, or null for a scene with no such moment. */
  contactAt: number | null;
  /** Where the carrier was, in metres, at that moment (worked out once, on first use). */
  contactSpot?: Vec;
}

const unit = (v: Vec): Vec => {
  const length = Math.hypot(v.x, v.y);
  return length < 1e-9 ? { x: 1, y: 0 } : { x: v.x / length, y: v.y / length };
};

/** A repeatable number in [0, 1) from text, so a choice made from it never changes between plays. */
function hashUnit(text: string): number {
  let value = 2166136261;
  for (let index = 0; index < text.length; index++) value = Math.imul(value ^ text.charCodeAt(index), 16777619);
  return ((value ^ (value >>> 15)) >>> 0) / 4294967296;
}

export function metresOf(player: { x: number; y: number }): Vec {
  return { x: player.x * PITCH_LENGTH_M, y: player.y * PITCH_WIDTH_M };
}

export class ScenePlanner {
  private readonly store: MatchStore;
  private readonly meta: ReplayMeta;
  private readonly plans = new Map<Contest, Plan | null>();

  constructor(store: MatchStore, meta: ReplayMeta) {
    this.store = store;
    this.meta = meta;
  }

  /** The plan for a contest, or null when it is left as the replay has it. Worked out once. */
  planOf(contest: Contest): Plan | null {
    if (this.plans.has(contest)) return this.plans.get(contest) ?? null;
    const plan = this.makePlan(contest);
    this.plans.set(contest, plan);
    return plan;
  }

  /** A player where the replay has him at `t`, or null if he is not on the pitch. */
  playerAt(id: string, t: number): SamplePlayer | null {
    const sample = sampleAt(this.frames, Math.max(t, 0));
    return sample?.players.find((player) => player.id === id) ?? null;
  }

  private get frames(): readonly Frame[] {
    return this.store.frames;
  }

  private makePlan(contest: Contest): Plan | null {
    switch (contest.kind) {
      case "dribble":
        return this.dribblePlan(contest);
      case "tackle":
        return this.tacklePlan(contest);
      case "header":
        return this.headerPlan(contest);
      case "restart":
        return this.restartPlan(contest);
    }
  }

  // ---- Plans ----

  private dribblePlan(contest: Extract<Contest, { kind: "dribble" }>): Plan | null {
    const attacker = contest.playerId;
    if (contest.outcome === "success") {
      const move = contest.move;
      if (move === null) return null;
      const script = MOVE_SCRIPTS[move];
      // A move that works has no challenge to bring a defender in from behind: he stays where the replay has him.
      return this.duel(contest, attacker, this.nearestOpponent(attacker, contest.t), {
        needsDefender: false,
        build: (approach) => (approach > 0 ? script : null),
        start: () => contest.t,
        contact: () => MOVE_CHALLENGE_AT[move],
      });
    }
    const mode = this.challengeMode(attacker, contest.t, contest.outcome === "lost" ? "lost" : "tackled");
    const make = (approach: Approach): Script => (contest.move === null ? tackleScript(mode, approach) : failedMove(contest.move, mode, approach));
    const loss = this.lossTime(attacker, contest.t);
    const start = loss - (make(1).contactAt ?? 0);
    const winner = mode === "won" || mode === "slide_won" || mode === "lost" ? this.nextCarrierFrom(attacker, loss) : null;
    return this.duel(contest, attacker, winner ?? this.nearestOpponent(attacker, start), {
      needsDefender: mode !== "lost",
      build: make,
      start: () => start,
      contact: (script) => script.contactAt ?? 0,
    });
  }

  private tacklePlan(contest: Extract<Contest, { kind: "tackle" }>): Plan | null {
    const attacker = contest.targetId;
    // A take-on that ends in a tackle is already a scene of its own.
    const covered = this.store.contests.some((other) => other.kind === "dribble" && other.outcome !== "success" && other.playerId === attacker && Math.abs(other.t - contest.t) <= 1.5);
    if (covered) return null;
    const slide = hashUnit(`${contest.tacklerId}${contest.t}`) < SLIDE_SHARE;
    const mode: ChallengeMode = contest.outcome === "missed" ? "missed" : contest.outcome === "foul" ? (slide ? "slide_foul" : "foul") : slide ? "slide_won" : "won";
    const make = (approach: Approach): Script => tackleScript(mode, approach);
    const start = contest.outcome === "won" ? this.lossTime(attacker, contest.t) - (make(1).contactAt ?? 0) : contest.t;
    return this.duel(contest, attacker, contest.tacklerId, { needsDefender: true, build: make, start: () => start, contact: (script) => script.contactAt ?? 0 });
  }

  private headerPlan(contest: Extract<Contest, { kind: "header" }>): Plan | null {
    const script = headerScript("shot");
    const attacker = contest.playerId;
    const side = teamOf(this.meta, attacker);
    const homeDir = this.frames[Math.min(Math.floor(contest.t), this.frames.length - 1)]?.homeDir ?? 1;
    const direction = side === "away" ? -homeDir : homeDir;
    const start = contest.t - HEADER_CONTACT_S;
    // The marker stands beside the jump whichever side of him the replay has him, so he is never brought round from behind.
    return this.duel(contest, attacker, this.nearestOpponent(attacker, start), {
      needsDefender: false,
      build: () => script,
      start: () => start,
      contact: () => HEADER_CONTACT_S,
      forward: { x: direction, y: 0 },
      fromBehind: false,
    });
  }

  private restartPlan(contest: Extract<Contest, { kind: "restart" }>): Plan | null {
    if (contest.restart === "throw_in") return null;
    const kick = kickTime(this.frames, contest.t);
    const available = kick - Math.max(contest.t, kick - KICK_TOUCH_S);
    if (available < 1.4) return null;
    const scale = Math.max(1, KICK_TOUCH_S / available);
    const back = contest.restart === "corner" ? 3.2 : contest.restart === "goal_kick" ? 3.6 : contest.restart === "penalty" ? 5 : 4;
    const script = kickScript(back);
    const aim = this.kickAim(kick, contest.takerId);
    const start = kick - KICK_TOUCH_S / scale;
    const wall = contest.restart === "free_kick" ? this.wallOf(contest.takerId, kick, aim) : [];
    const run = { forward: aim, inward: this.inwardOf(contest.takerId, Math.max(start, 0), aim) };
    return this.finish(contest, script, contest.takerId, null, start, scale, wall, run);
  }

  private finish(contest: Contest, script: Script, attacker: string, defender: string | null, start: number, scale: number, wall: string[], run: RunFrame, contactAt: number | null = null): Plan {
    return { start, scale, script, attacker, defender, wall, forward: run.forward, inward: run.inward, foot: this.footOf(attacker, contest.t, run.forward), side: defenderSide(script), contactAt };
  }

  /**
   * A scene between the carrier and a defender, built for the way the replay actually has the two:
   * a defender too far off to reach him is left out, one behind him is brought in chasing from behind,
   * one on the outside is put there, and a long way to cover gets a longer run in, so nobody ever
   * crosses the carrier's body or dashes across the pitch.
   */
  private duel(contest: Contest, attacker: string, defender: string | null, option: Duel): Plan | null {
    const probe = option.build(1);
    if (probe === null) return null;
    const start = option.start(probe);
    const run = option.forward === undefined ? this.runFrame(attacker, Math.max(start, 0)) : { forward: option.forward, inward: this.inwardOf(attacker, Math.max(start, 0), option.forward) };
    const contactAt = start + option.contact(probe);
    let relation = defender === null ? null : this.relation(attacker, defender, contactAt, run);
    if (relation !== null && relation.distance > REACH_MAX_M) relation = null;
    if (relation === null && option.needsDefender) return null;
    const approach: Approach = relation !== null && option.fromBehind !== false && relation.f < -BEHIND_FROM_M ? -1 : 1;
    const script = approach > 0 ? probe : option.build(approach);
    if (script === null) {
      // Nothing to bring in from behind, and the scene works without him.
      return option.needsDefender ? null : this.finish(contest, probe, attacker, null, start, 1, [], run, option.contact(probe));
    }
    let inward = run.inward;
    if (relation !== null && Math.abs(relation.l) > SIDE_DEADBAND_M && (relation.l >= 0 ? 1 : -1) !== defenderSide(script)) {
      inward = { x: -inward.x, y: -inward.y };
    }
    const placed: RunFrame = { forward: run.forward, inward };
    const sees = (found: Relation | null): Relation | null => (found === null || inward === run.inward ? found : { ...found, l: -found.l });
    const atStart = defender === null ? null : sees(this.relation(attacker, defender, Math.max(start, 0), run));
    const atContact = sees(relation);
    const lead = atContact === null ? 0 : this.leadFor(script, option.contact(script), atStart, atContact);
    return this.finish(contest, withLeadIn(script, lead), attacker, relation === null ? null : defender, start - lead, 1, [], placed, option.contact(script) + lead);
  }

  /**
   * Seconds of run in a defender needs: the longer the way from where the replay has him to where
   * the script wants him (first for the start of his approach, then for the contact), the longer
   * he is given to get there at a man's pace.
   */
  private leadFor(script: Script, contact: number, atStart: Relation | null, atContact: Relation): number {
    const first = script.defender[0];
    const second = script.defender[1] ?? first;
    const spot = defenderAt(script, contact);
    const forContact = (Math.hypot(spot.f - atContact.f, spot.l - atContact.l) * spot.w) / CLOSE_PACE_MPS - contact;
    const forStart = first === undefined || second === undefined || atStart === null ? 0 : (Math.hypot(second.f - atStart.f, second.l - atStart.l) * second.w) / CLOSE_PACE_MPS - (second.s - first.s);
    return Math.min(Math.max(forContact, forStart, 0), MAX_LEAD_S);
  }

  /** Where the defender is from the carrier at `t`, along his run (`f`) and toward the middle (`l`), in metres. */
  private relation(attacker: string, defender: string, t: number, run: RunFrame): Relation | null {
    const a = this.playerAt(attacker, t);
    const d = this.playerAt(defender, t);
    if (a === null || d === null) return null;
    const offset = { x: (d.x - a.x) * PITCH_LENGTH_M, y: (d.y - a.y) * PITCH_WIDTH_M };
    return { f: offset.x * run.forward.x + offset.y * run.forward.y, l: offset.x * run.inward.x + offset.y * run.inward.y, distance: Math.hypot(offset.x, offset.y) };
  }

  // ---- Reading the replay ----

  /** The way the carrier runs at `t` and which way is toward the middle of the pitch. */
  private runFrame(attacker: string, t: number): RunFrame {
    const player = this.playerAt(attacker, t);
    if (player === null) return { forward: { x: 1, y: 0 }, inward: { x: 0, y: 1 } };
    let forward: Vec = { x: player.vx, y: player.vy };
    if (Math.hypot(forward.x, forward.y) < 0.8) {
      const later = this.playerAt(attacker, t + 3);
      const here = metresOf(player);
      const there = later === null ? here : metresOf(later);
      forward = Math.hypot(there.x - here.x, there.y - here.y) > 2 ? { x: there.x - here.x, y: there.y - here.y } : { x: 1, y: 0 };
    }
    const direction = unit(forward);
    return { forward: direction, inward: this.inwardOf(attacker, t, direction) };
  }

  private inwardOf(attacker: string, t: number, forward: Vec): Vec {
    const player = this.playerAt(attacker, t);
    const across = { x: -forward.y, y: forward.x };
    const towardMiddle = player === null ? 1 : player.y > 0.5 ? -1 : 1;
    return across.y * towardMiddle >= 0 ? across : { x: -across.x, y: -across.y };
  }

  private nearestOpponent(attacker: string, t: number): string | null {
    const sample = sampleAt(this.frames, Math.max(t, 0));
    const me = sample?.players.find((player) => player.id === attacker);
    if (sample === null || me === undefined) return null;
    const side = teamOf(this.meta, attacker);
    let best: { id: string; gap: number } | null = null;
    for (const player of sample.players) {
      if (teamOf(this.meta, player.id) === side) continue;
      const gap = Math.hypot((player.x - me.x) * PITCH_LENGTH_M, (player.y - me.y) * PITCH_WIDTH_M);
      if (best === null || gap < best.gap) best = { id: player.id, gap };
    }
    return best?.id ?? null;
  }

  /** The first moment after `from` that the ball is no longer held by `attacker` (or `from` plus three seconds). */
  private lossTime(attacker: string, from: number): number {
    for (let index = Math.max(Math.floor(from), 0); index < Math.min(this.frames.length, Math.floor(from) + SEARCH_S); index++) {
      if (this.frames[index]?.carrierId !== attacker) return index;
    }
    return from + 3;
  }

  private nextCarrierFrom(attacker: string, t: number): string | null {
    const side = teamOf(this.meta, attacker);
    for (let step = 0; step <= 4; step++) {
      const id = this.frames[Math.min(Math.floor(t) + step, this.frames.length - 1)]?.carrierId;
      if (id !== null && id !== undefined && teamOf(this.meta, id) !== side) return id;
    }
    return null;
  }

  private challengeMode(attacker: string, t: number, outcome: "tackled" | "lost"): ChallengeMode {
    if (outcome === "lost") return "lost";
    const fouled = this.store.log.some((event) => event.type === "foul" && event.targetId === attacker && event.t >= t - 1 && event.t <= t + 8);
    const slide = hashUnit(`${attacker}${t}`) < SLIDE_SHARE;
    return fouled ? (slide ? "slide_foul" : "foul") : slide ? "slide_won" : "won";
  }

  private kickAim(kick: number, taker: string): Vec {
    const now = this.frames[Math.min(Math.floor(kick), this.frames.length - 1)];
    const next = this.frames[Math.min(Math.floor(kick) + 1, this.frames.length - 1)];
    if (now !== undefined && next !== undefined) {
      const dx = (next.ballX - now.ballX) * PITCH_LENGTH_M;
      const dy = (next.ballY - now.ballY) * PITCH_WIDTH_M;
      if (Math.hypot(dx, dy) > 2) return unit({ x: dx, y: dy });
    }
    const side = teamOf(this.meta, taker);
    const homeDir = now?.homeDir ?? 1;
    return { x: side === "away" ? -homeDir : homeDir, y: 0 };
  }

  private wallOf(taker: string, kick: number, aim: Vec): string[] {
    const sample = sampleAt(this.frames, Math.max(kick - 1, 0));
    const me = sample?.players.find((player) => player.id === taker);
    if (sample === null || me === undefined) return [];
    const side = teamOf(this.meta, taker);
    const here = metresOf(me);
    const found: { id: string; gap: number }[] = [];
    for (const player of sample.players) {
      if (teamOf(this.meta, player.id) === side) continue;
      const there = metresOf(player);
      const offset = { x: there.x - here.x, y: there.y - here.y };
      const gap = Math.hypot(offset.x, offset.y);
      if (gap < WALL_MIN_M || gap > WALL_MAX_M) continue;
      const along = (offset.x * aim.x + offset.y * aim.y) / gap;
      if (along < Math.cos(WALL_ANGLE)) continue;
      found.push({ id: player.id, gap });
    }
    return found.sort((a, b) => a.gap - b.gap).slice(0, WALL_SIZE).map((entry) => entry.id);
  }

  /** Which foot he uses: his preferred foot, or sometimes his weaker one, chosen the same way every time. */
  private footOf(attacker: string, t: number, forward: Vec): Foot {
    const side = teamOf(this.meta, attacker);
    const player = side === null ? undefined : this.meta[side].players[attacker];
    const preferred = player?.preferred_foot ?? "right";
    const weakness = (100 - (player?.weak_foot ?? 50)) / 100;
    const draw = hashUnit(`${attacker}${Math.floor(t)}`);
    const rightPreferred = preferred === "right" ? true : preferred === "left" ? false : hashUnit(attacker) < 0.5;
    const useWeak = preferred !== "both" && draw < WEAK_FOOT_SHARE * weakness;
    const wantsRight = useWeak ? !rightPreferred : rightPreferred;
    // Seen from the touchline, a player running to the right shows his right side and one running left his left.
    return wantsRight === forward.x >= 0 ? "near" : "far";
  }
}
