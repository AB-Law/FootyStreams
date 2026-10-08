import type { ReplayMeta, TeamSide } from "./meta.ts";
import { teamOf } from "./meta.ts";
import { KEEPER_COLOURS, pickKits, type Kit } from "./palette.ts";
import { drawPitch, toScreen } from "./pitch.ts";
import type { Sample } from "./interpolate.ts";
import { drawBall, drawCarrierMark, drawPlayer, type Dress } from "./sprites.ts";

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

  draw(ctx: CanvasRenderingContext2D, sample: Sample | null, clock: number): void {
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
      const at = toScreen(player.x, player.y);
      drawPlayer(ctx, at.x, at.y, dress, player.running, clock);
    }
    const carrier = sample.carrierId === null ? null : this.screenPosition(sample, sample.carrierId);
    if (carrier !== null) drawCarrierMark(ctx, carrier.x, carrier.y);
    const ball = toScreen(sample.ballX, sample.ballY);
    drawBall(ctx, ball.x, ball.y);
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
