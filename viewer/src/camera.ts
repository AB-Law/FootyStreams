import { sampleAt } from "./interpolate.ts";
import { HEIGHT, WIDTH, toScreen } from "./pitch.ts";
import type { Frame } from "./store.ts";

/** The camera looks at the ball as it was over the last moments, so it glides rather than jerks. */
const FOLLOW_SECONDS = 1.5;
const FOLLOW_SAMPLES = 4;
/** The ball may drift this far from the middle of the view (share of half the view) before it pulls. */
const SLACK = 0.55;

export const ZOOMS = [1, 2, 3] as const;
export type Zoom = (typeof ZOOMS)[number];

/** A window on the world: `x`, `y` is its top-left corner in world pixels, `zoom` the magnification. */
export interface Camera {
  x: number;
  y: number;
  zoom: number;
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

/** Where the camera is at `t`: centred on the recent ball, with the ball never near the edge. */
export function cameraAt(frames: readonly Frame[], t: number, zoom: number): Camera {
  const width = WIDTH / zoom;
  const height = HEIGHT / zoom;
  if (zoom <= 1) return { x: 0, y: 0, zoom: 1 };
  let centreX = 0;
  let centreY = 0;
  let ball = { x: WIDTH / 2, y: HEIGHT / 2 };
  for (let step = 0; step < FOLLOW_SAMPLES; step++) {
    const sample = sampleAt(frames, t - (step * FOLLOW_SECONDS) / (FOLLOW_SAMPLES - 1));
    if (sample === null) continue;
    const at = toScreen(sample.ballX, sample.ballY);
    if (step === 0) ball = at;
    centreX += at.x / FOLLOW_SAMPLES;
    centreY += at.y / FOLLOW_SAMPLES;
  }
  // Keep the ball inside the middle of the view even when it is moving faster than the average.
  centreX = clamp(centreX, ball.x - SLACK * (width / 2), ball.x + SLACK * (width / 2));
  centreY = clamp(centreY, ball.y - SLACK * (height / 2), ball.y + SLACK * (height / 2));
  return { x: clamp(centreX - width / 2, 0, WIDTH - width), y: clamp(centreY - height / 2, 0, HEIGHT - height), zoom };
}

/** A point in the world as it appears on the 320x180 screen. */
export function toView(camera: Camera, point: { x: number; y: number }): { x: number; y: number } {
  return { x: (point.x - camera.x) * camera.zoom, y: (point.y - camera.y) * camera.zoom };
}
