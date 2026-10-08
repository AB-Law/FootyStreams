export const SPEEDS = [1, 4, 16] as const;
export type Speed = (typeof SPEEDS)[number];

/** The replay clock: match seconds advancing at `speed` times real time. */
export class Playback {
  t = 0;
  speed: Speed = 1;
  playing = false;

  /** Move on by `realSeconds` (times `boost`, to hurry through dead time); stops at `duration`. */
  advance(realSeconds: number, duration: number, boost = 1): void {
    if (!this.playing) return;
    this.t = Math.min(this.t + realSeconds * this.speed * boost, duration);
    if (this.t >= duration) this.playing = false;
  }

  seek(t: number, duration: number): void {
    this.t = Math.min(Math.max(t, 0), duration);
  }

  /** Play or pause; playing from the end starts over. */
  toggle(duration: number): void {
    if (!this.playing && this.t >= duration) this.t = 0;
    this.playing = !this.playing;
  }
}
