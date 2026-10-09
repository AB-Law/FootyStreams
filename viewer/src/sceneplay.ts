import { DEFENDER_RECOVERY_S, keepApart, playScript, type Lying } from "./choreo.ts";
import { STANCES, blendJoints, gaitFor, swing, type Joints } from "./figure.ts";
import type { Sample, SamplePlayer } from "./interpolate.ts";
import type { ReplayMeta } from "./meta.ts";
import { PITCH_LENGTH_M, PITCH_WIDTH_M, SEARCH_S, ScenePlanner, metresOf, type Plan, type Vec } from "./sceneplan.ts";
import type { Contest, MatchStore } from "./store.ts";

// Plays the plans from sceneplan.ts over a replay. The carrier is where the replay has him plus the
// scene's offsets, the ball and the defender follow the script, and in the last moments everything
// is eased back onto the replay's own positions so nothing jumps.

const HANDOFF_S = 0.35;
/** A scene still plays this long after its script ends, so a beaten defender can recover. */
const TAIL_S = DEFENDER_RECOVERY_S;
/** Two players in a scene are never drawn closer than this, whatever their paths do. */
const MIN_APART_M = 0.8;
/** A defender eases back to where the replay has him over this long, longer than the carrier as he has further to go. */
const DEFENDER_HANDOFF_S = 0.9;
/** After contact the defender and a loose ball stay where the contact was, as the carrier runs on, over this long. */
const ANCHOR_S = 0.35;

/** How one player is posed by a scene: where he is shifted to (metres), how he stands and faces. */
export interface PlayerPose {
  joints: Joints;
  /** Shift from his replay position, in metres along and across the pitch. */
  dxM: number;
  dyM: number;
  /** Height off the ground in metres (a jump). */
  h: number;
  /** +1 faces toward x = 1, -1 toward x = 0. */
  facing: 1 | -1;
  lying: Lying | null;
}

export interface SceneFrame {
  poses: Map<string, PlayerPose>;
  /** The ball where a scene puts it (fractions of the pitch, and metres of height), or null for the replay's own. */
  ball: { x: number; y: number; h: number } | null;
}

const smooth = (u: number): number => u * u * (3 - 2 * u);
const clamp01 = (u: number): number => Math.min(Math.max(u, 0), 1);

export class ScenePlayer {
  private readonly store: MatchStore;
  private readonly planner: ScenePlanner;

  constructor(store: MatchStore, meta: ReplayMeta) {
    this.store = store;
    this.planner = new ScenePlanner(store, meta);
  }

  /** The plan a contest is played from, or null when it is left as the replay has it (for tools that inspect scenes). */
  planOf(contest: Contest): Plan | null {
    return this.planner.planOf(contest);
  }

  /** The scenes under way at `t`, as poses for the players in them and, if one holds it, the ball. */
  at(t: number, sample: Sample | null): SceneFrame {
    const frame: SceneFrame = { poses: new Map(), ball: null };
    if (sample === null) return frame;
    const contests = this.store.contests;
    for (let index = contests.length - 1; index >= 0; index--) {
      const contest = contests[index];
      if (contest === undefined) continue;
      if (contest.t > t + 4) continue;
      if (t - contest.t > SEARCH_S + 6) break;
      const plan = this.planner.planOf(contest);
      if (plan === null) continue;
      const s = (t - plan.start) * plan.scale;
      if (s < -0.05 || s > plan.script.duration + TAIL_S) continue;
      this.play(plan, s, t, sample, frame);
    }
    return frame;
  }

  private play(plan: Plan, s: number, t: number, sample: Sample, out: SceneFrame): void {
    const attacker = sample.players.find((player) => player.id === plan.attacker);
    if (attacker === undefined) return;
    const home = metresOf(attacker);
    const speed = Math.hypot(attacker.vx, attacker.vy);
    const gait = gaitFor(speed);
    const phase = t;
    const amp = plan.script.body.some((key) => key.stance === "hips") ? 1 : gait.amp;
    const raw = playScript(plan.script, Math.min(s, plan.script.duration + TAIL_S), phase / gait.period, amp, plan.foot);
    const play = keepApart(raw, plan.side);
    const handoff = smooth(clamp01((s - (plan.script.duration - HANDOFF_S)) / HANDOFF_S));
    const handoffDefender = smooth(clamp01((s - (plan.script.duration - DEFENDER_HANDOFF_S)) / DEFENDER_HANDOFF_S));
    const keep = 1 - handoff;
    const held = this.heldFrom(plan, s, home, attacker);
    const relax = (joints: Joints, own: SamplePlayer): Joints => blendJoints(joints, swing(phase / gaitFor(Math.hypot(own.vx, own.vy)).period, gaitFor(Math.hypot(own.vx, own.vy)).amp), handoff);
    const world = (f: number, l: number): Vec => ({ x: plan.forward.x * f + plan.inward.x * l, y: plan.forward.y * f + plan.inward.y * l });
    // A figure faces the way the carrier runs, or against it if it is the man meeting him, unless `turn` swings him round.
    const faces = (turn: boolean, withRunner: boolean): 1 | -1 => {
      const along = withRunner !== turn ? plan.forward.x : -plan.forward.x;
      return along >= 0 ? 1 : -1;
    };
    const shift = world(play.attacker.f * keep, play.attacker.l * keep);
    out.poses.set(plan.attacker, {
      joints: relax(play.attacker.joints, attacker),
      dxM: shift.x,
      dyM: shift.y,
      h: play.attacker.h * keep,
      facing: faces(play.attacker.turn, true),
      lying: handoff > 0.9 ? null : play.attacker.lying,
    });
    const attackerAt = { x: home.x + shift.x, y: home.y + shift.y };
    const defenderAt = plan.defender === null ? null : this.playDefender(plan, play, sample, held, attackerAt, handoffDefender, out, faces, relax);
    for (const id of plan.wall) this.playWall(plan, play, sample, id, handoff, out, relax);
    const owner = plan.script.owner === "attacker" ? { posed: attackerAt, real: home } : plan.script.owner === "defender" ? defenderAt : null;
    // The ball goes back to the replay with whoever has it: the defender's handoff is the longer one.
    const ballHandoff = plan.script.owner === "defender" ? handoffDefender : handoff;
    this.playBall(plan, play, sample, plan.script.owner === "attacker" ? home : held, s, ballHandoff, out, world, owner);
  }

  /**
   * Where the scene's offsets are measured from. They follow the carrier as he runs until the contact,
   * and from then on they stay where the contact was: he runs on, and the man who won the ball, or
   * the ball he lost, is left behind rather than dragged along with him.
   */
  private heldFrom(plan: Plan, s: number, home: Vec, attacker: SamplePlayer): Vec {
    if (plan.contactAt === null) return home;
    if (plan.contactSpot === undefined) {
      const there = this.planner.playerAt(plan.attacker, plan.start + plan.contactAt / plan.scale);
      plan.contactSpot = metresOf(there ?? attacker);
    }
    const k = smooth(clamp01((s - plan.contactAt + 0.1) / ANCHOR_S));
    return { x: home.x + (plan.contactSpot.x - home.x) * k, y: home.y + (plan.contactSpot.y - home.y) * k };
  }

  /** Poses the defender and returns where he is drawn and where the replay has him, in metres (null if he is not on the pitch). */
  private playDefender(
    plan: Plan,
    play: ReturnType<typeof playScript>,
    sample: Sample,
    home: Vec,
    attackerAt: Vec,
    handoff: number,
    out: SceneFrame,
    faces: (turn: boolean, withRunner: boolean) => 1 | -1,
    relax: (joints: Joints, own: SamplePlayer) => Joints,
  ): { posed: Vec; real: Vec } | null {
    const defender = sample.players.find((player) => player.id === plan.defender);
    if (defender === undefined) return null;
    const pull = play.defender.w * (1 - handoff);
    const real = metresOf(defender);
    const target = { x: home.x + plan.forward.x * play.defender.f + plan.inward.x * play.defender.l, y: home.y + plan.forward.y * play.defender.f + plan.inward.y * play.defender.l };
    const stance = Math.max(play.defender.stanceW, pull);
    const pulled = { x: real.x + (target.x - real.x) * pull, y: real.y + (target.y - real.y) * pull };
    // Held clear of the carrier only while the scene has him; as he eases back to the replay the hold lets go.
    const held = this.clear(pulled, attackerAt, plan);
    const grip = clamp01(pull * 3);
    const posed = { x: pulled.x + (held.x - pulled.x) * grip, y: pulled.y + (held.y - pulled.y) * grip };
    out.poses.set(plan.defender as string, {
      joints: blendJoints(relax(STANCES.jockey, defender), play.defender.joints, stance),
      dxM: posed.x - real.x,
      dyM: posed.y - real.y,
      h: play.defender.h,
      facing: faces(play.defender.turn, false),
      lying: handoff > 0.9 ? null : play.defender.lying,
    });
    return { posed, real };
  }

  /**
   * The spot pushed out to `MIN_APART_M` from `other` if it is closer, so two players are never drawn
   * on top of each other. The direction leans toward the scene's side the closer it is, so a path
   * that runs through him swings round him on that side rather than flipping to the other.
   */
  private clear(spot: Vec, other: Vec, plan: Plan): Vec {
    const offset = { x: spot.x - other.x, y: spot.y - other.y };
    const gap = Math.hypot(offset.x, offset.y);
    if (gap >= MIN_APART_M) return spot;
    const lean = plan.side * (MIN_APART_M - gap);
    const toward = { x: offset.x + plan.inward.x * lean, y: offset.y + plan.inward.y * lean };
    const length = Math.hypot(toward.x, toward.y);
    const away = length < 1e-6 ? { x: plan.inward.x * plan.side, y: plan.inward.y * plan.side } : { x: toward.x / length, y: toward.y / length };
    return { x: other.x + away.x * MIN_APART_M, y: other.y + away.y * MIN_APART_M };
  }

  private playWall(plan: Plan, play: ReturnType<typeof playScript>, sample: Sample, id: string, handoff: number, out: SceneFrame, relax: (joints: Joints, own: SamplePlayer) => Joints): void {
    const member = sample.players.find((player) => player.id === id);
    if (member === undefined) return;
    out.poses.set(id, {
      joints: blendJoints(relax(STANCES.jockey, member), play.defender.joints, play.defender.stanceW),
      dxM: 0,
      dyM: 0,
      h: play.defender.h * (1 - handoff),
      facing: plan.forward.x >= 0 ? -1 : 1,
      lying: null,
    });
  }

  /**
   * The ball where the script puts it, handed back to the replay as the scene ends: it is held
   * against whoever has it, so as that player eases onto his replay place the ball goes with him.
   */
  private playBall(
    plan: Plan,
    play: ReturnType<typeof playScript>,
    sample: Sample,
    home: Vec,
    s: number,
    handoff: number,
    out: SceneFrame,
    world: (f: number, l: number) => Vec,
    owner: { posed: Vec; real: Vec } | null,
  ): void {
    const script = plan.script;
    if (script.ballUntil !== undefined && s > script.ballUntil) return;
    const fadeIn = script.ballFrom === undefined ? 1 : smooth(clamp01((s - script.ballFrom) / 0.3));
    if (fadeIn <= 0 || handoff >= 1) return;
    const spot = world(play.ball.f, play.ball.l);
    const real = { x: sample.ballX * PITCH_LENGTH_M, y: sample.ballY * PITCH_WIDTH_M };
    const scripted = { x: home.x + spot.x, y: home.y + spot.y };
    const held = owner === null ? real : { x: owner.posed.x + real.x - owner.real.x, y: owner.posed.y + real.y - owner.real.y };
    const x = scripted.x + (held.x - scripted.x) * handoff;
    const y = scripted.y + (held.y - scripted.y) * handoff;
    out.ball = { x: (real.x + (x - real.x) * fadeIn) / PITCH_LENGTH_M, y: (real.y + (y - real.y) * fadeIn) / PITCH_WIDTH_M, h: play.ball.h * (1 - handoff) * fadeIn };
  }
}
