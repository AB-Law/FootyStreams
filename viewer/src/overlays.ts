import type { Mark } from "./store.ts";

/** How long each overlay stays up, in real seconds at the current speed. */
export const OVERLAY_SECONDS: Record<Mark["kind"], number> = {
  goal: 4.5,
  card: 2.5,
  foul: 1.5,
  substitution: 4,
  halftime: 3,
  fulltime: 3,
};

export interface ActiveOverlay {
  mark: Mark;
  /** 0 when it appears, approaching 1 as it leaves. */
  progress: number;
}

/**
 * The overlays showing at match time `t`.
 *
 * `speed` stretches the window in match seconds so a banner stays readable at 4x and 16x.
 */
export function overlaysAt(marks: readonly Mark[], t: number, speed: number): ActiveOverlay[] {
  const active: ActiveOverlay[] = [];
  for (const mark of marks) {
    const window = OVERLAY_SECONDS[mark.kind] * speed;
    if (t >= mark.t && t < mark.t + window) active.push({ mark, progress: (t - mark.t) / window });
  }
  return active;
}
