import type { ReplayMeta, TeamSide } from "./meta.ts";
import { teamOf } from "./meta.ts";
import { KEEPER_COLOURS, pickKits, type Kit } from "./palette.ts";
import { PITCH, drawPitch, toScreen } from "./pitch.ts";
import type { Sample } from "./interpolate.ts";
import { ballOnFlight, type Flight } from "./flights.ts";
import type { Pos } from "./events.ts";
import { drawText } from "./font.ts";
import type { Pose } from "./poses.ts";
import { drawBall, drawCarrierMark, drawFocusMark, drawPlayer, drawTrail, type Dress } from "./sprites.ts";

/** Everything besides the sampled frame that changes what is on screen at one moment. */
export interface Extras {
  /** The ball in the air, if a pass or shot is under way: it replaces the frame's ball. */
  flight: Flight | null;
  t: number;
  referee: Pos | null;
  /** True while the referee has just stopped play for a foul or a card. */
  whistle: boolean;
  /** True when the camera is zoomed in, so the large sprites are used. */
  big: boolean;
  /** Players in a tackle, a fall or a take-on, by id. */
  poses: ReadonlyMap<string, Pose>;
  /** A player the viewer asked to follow: he is marked on the pitch. */
  focusId?: string | null;
}

const REFEREE_KIT = { pattern: "solid", primary: "#d8c04a", secondary: "#14171c" } as const;
const REFEREE_LOOK = { skin_tone: 3, hair_style: "short", hair_colour: "black", facial_hair: "none", build: "lean" };
/** The feet may stand right on the touchline (a throw-in is taken there); the sim keeps others off it. */
const TOP_CLEARANCE_PX = 0;
/** The ball sits at a player's feet, not under them. */
const BALL_AT_FEET_PX = 2;
const LABEL_COLOUR = "#d8c04a";

/** Draws the pitch, the 22 players and the ball for one sample. Overlays are drawn on top by hud.ts. */
export class Scene {
  private readonly meta: ReplayMeta;
  private readonly kits: Record<TeamSide, Kit>;

  constructor(meta: ReplayMeta) {
    this.meta = meta;
    this.kits = pickKits(meta);
  }

  /** Where a player is on screen in this sample, or null when he is not on the pitch. */
  screenPosition(sample: Sample, playerId: string): { x: number; y: number } | null {
    const player = sample.players.find((candidate) => candidate.id === playerId);
    return player === undefined ? null : toScreen(player.x, player.y);
  }

  draw(ctx: CanvasRenderingContext2D, sample: Sample | null, extras: Extras): void {
    drawPitch(ctx);
    if (sample === null) return;
    const keepers = this.keeperIds(sample);
    const ordered = [...sample.players].sort((a, b) => a.y - b.y);
    for (const player of ordered) {
      const side = teamOf(this.meta, player.id);
      const meta = side === null ? undefined : this.meta[side].players[player.id];
      if (side === null || meta === undefined) continue;
      const dress: Dress = {
        kit: this.kits[side],
        keeper: keepers.has(player.id) ? KEEPER_COLOURS[side] : null,
        appearance: meta.appearance,
      };
      const pose = extras.poses.get(player.id);
      const base = toScreen(player.x, player.y);
      const at = this.onPitch({ x: base.x + (pose?.dx ?? 0), y: base.y + (pose?.dy ?? 0) });
      const lying = pose !== undefined && (pose.name === "slide" || pose.name === "fall") ? pose.facing : undefined;
      if (player.id === extras.focusId) drawFocusMark(ctx, at.x, at.y, extras.big);
      drawPlayer(ctx, at.x, at.y, dress, { running: player.running || pose !== undefined, phase: extras.t, big: extras.big, lying, arms: pose?.name === "throw" });
    }
    if (extras.referee !== null) this.drawReferee(ctx, extras.referee, extras);
    this.drawTheBall(ctx, sample, extras);
  }

  private drawTheBall(ctx: CanvasRenderingContext2D, sample: Sample, extras: Extras): void {
    if (extras.flight === null) {
      const carrier = sample.carrierId === null ? null : this.screenPosition(sample, sample.carrierId);
      if (carrier !== null) drawCarrierMark(ctx, carrier.x, carrier.y, extras.big);
      const resting = toScreen(sample.ballX, sample.ballY);
      const carried = extras.poses.get(sample.carrierId ?? "");
      const follows = carried?.ballFollows !== false;
      const shiftX = follows ? (carried?.dx ?? 0) : 0;
      const shiftY = follows ? (carried?.dy ?? 0) : 0;
      drawBall(ctx, resting.x + BALL_AT_FEET_PX + shiftX, resting.y + shiftY, sample.ballHeight + (carried?.ballLift ?? 0));
      return;
    }
    const flight = extras.flight;
    if (flight.fast) {
      const behind = [0.06, 0.12, 0.18].map((lag) => ballOnFlight(flight, extras.t - lag * (flight.t1 - flight.t0)));
      drawTrail(ctx, behind.map((point) => ({ ...toScreen(point.x, point.y), height: point.height })));
    }
    const point = ballOnFlight(flight, extras.t);
    const at = toScreen(point.x, point.y);
    drawBall(ctx, at.x, at.y, point.height);
  }

  private drawReferee(ctx: CanvasRenderingContext2D, spot: Pos, extras: Extras): void {
    const t = extras.t;
    const at = this.onPitch(toScreen(spot.x, spot.y));
    drawPlayer(ctx, at.x, at.y, { kit: REFEREE_KIT, keeper: null, appearance: REFEREE_LOOK }, { running: true, phase: t, big: extras.big });
    if (extras.whistle) drawText(ctx, "!", at.x - 1, at.y - 19, LABEL_COLOUR);
  }

  /** Keep a player's feet far enough inside the touchlines that he is drawn on the pitch. */
  private onPitch(point: { x: number; y: number }): { x: number; y: number } {
    const bottom = PITCH.y + PITCH.height - 1;
    return { x: point.x, y: Math.min(Math.max(point.y, PITCH.y + TOP_CLEARANCE_PX), bottom) };
  }

  /** The first player of each side in slot order is its goalkeeper. */
  private keeperIds(sample: Sample): Set<string> {
    const keepers = new Set<string>();
    const seen = new Set<TeamSide>();
    for (const player of sample.players) {
      const side = teamOf(this.meta, player.id);
      if (side !== null && !seen.has(side)) {
        seen.add(side);
        keepers.add(player.id);
      }
    }
    return keepers;
  }
}
