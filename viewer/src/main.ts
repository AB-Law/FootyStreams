import { ZOOMS, cameraAt, type Zoom } from "./camera.ts";
import { deadSpans, isDead } from "./deadtime.ts";
import { drawText } from "./font.ts";
import { drawOverlays, drawScoreboard } from "./hud.ts";
import { sampleAt } from "./interpolate.ts";
import type { ReplayMeta } from "./meta.ts";
import { activeFlight } from "./flights.ts";
import { overlaysAt } from "./overlays.ts";
import { posesAt } from "./poses.ts";
import { refereeTrack } from "./referee.ts";
import { pickKits } from "./palette.ts";
import { Playback, SPEEDS } from "./playback.ts";
import { HEIGHT, WIDTH } from "./pitch.ts";
import { Scene } from "./scene.ts";
import { loadReplay } from "./source.ts";
import { MatchStore } from "./store.ts";

const FRAME_MILLISECONDS = 1000 / 30;
const DEFAULT_REPLAY = "replays/replay";
const DEFAULT_ZOOM: Zoom = 2;
/** Dead ball time (throw-ins, goal kicks, injuries) is played this much faster. */
const DEAD_TIME_BOOST = 3;

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`missing #${id}`);
  return found as T;
}

/** The largest whole-number scale that fits, so pixels stay square and crisp. */
function fitCanvas(canvas: HTMLCanvasElement): void {
  const scale = Math.max(1, Math.floor(Math.min(window.innerWidth / WIDTH, (window.innerHeight - 110) / HEIGHT)));
  canvas.style.width = `${WIDTH * scale}px`;
  canvas.style.height = `${HEIGHT * scale}px`;
}

function formatTime(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

async function start(): Promise<void> {
  const params = new URLSearchParams(location.search);
  const canvas = element<HTMLCanvasElement>("screen");
  const status = element<HTMLElement>("status");
  const context = canvas.getContext("2d");
  if (context === null) throw new Error("no 2d canvas");
  context.imageSmoothingEnabled = false;
  fitCanvas(canvas);
  window.addEventListener("resize", () => fitCanvas(canvas));

  // The file reader is the only source today; a live feed would call store.onEvent the same way.
  const store = new MatchStore();
  let meta: ReplayMeta;
  try {
    meta = await loadReplay(params.get("replay") ?? DEFAULT_REPLAY, (event) => store.onEvent(event));
  } catch (error) {
    status.textContent = String(error);
    return;
  }
  status.textContent = `${meta.home.name} v ${meta.away.name}`;

  const scene = new Scene(meta);
  const kits = pickKits(meta);
  const playback = new Playback();
  playback.seek(Number(params.get("t") ?? 0), store.duration);
  const scrubber = element<HTMLInputElement>("scrubber");
  const playButton = element<HTMLButtonElement>("play");
  const time = element<HTMLElement>("time");
  scrubber.max = String(Math.floor(store.duration));

  let zoom: Zoom = ZOOMS.includes(Number(params.get("zoom")) as Zoom) ? (Number(params.get("zoom")) as Zoom) : DEFAULT_ZOOM;
  const zoomButtons = ZOOMS.map((level) => {
    const button = element<HTMLButtonElement>(`zoom-${level}`);
    button.addEventListener("click", () => {
      zoom = level;
      zoomButtons.forEach((other) => other.classList.toggle("on", other === button));
      render();
    });
    button.classList.toggle("on", level === zoom);
    return button;
  });

  const stoppages = deadSpans(store.frames);
  const hurrying = (): boolean => playback.playing && isDead(stoppages, playback.t);

  const render = (): void => {
    const sample = sampleAt(store.frames, playback.t);
    const overlays = overlaysAt(store.marks, playback.t, playback.speed);
    const referee = refereeTrack(store.frames, store.marks, playback.t);
    const camera = cameraAt(store.frames, playback.t, zoom);
    context.save();
    context.setTransform(camera.zoom, 0, 0, camera.zoom, -camera.x * camera.zoom, -camera.y * camera.zoom);
    scene.draw(context, sample, {
      t: playback.t,
      flight: activeFlight(store.flights, playback.t),
      referee: referee === null ? null : referee.spot,
      whistle: referee?.incident ?? false,
      big: camera.zoom > 1,
      poses: posesAt(store.contests, sample, playback.t, store.frames),
    });
    context.restore();
    drawScoreboard(context, sample, meta, kits, playback.t >= store.duration);
    drawOverlays(context, overlays, meta, scene, sample, camera);
    if (hurrying()) drawText(context, ">>", WIDTH - 14, 24, "#ffd23f", 2);
    scrubber.value = String(Math.floor(playback.t));
    playButton.textContent = playback.playing ? "Pause" : "Play";
    time.textContent = `${formatTime(playback.t)} / ${formatTime(store.duration)}`;
  };

  playButton.addEventListener("click", () => playback.toggle(store.duration));
  scrubber.addEventListener("input", () => {
    playback.seek(Number(scrubber.value), store.duration);
    render();
  });
  const speedButtons = SPEEDS.map((speed) => {
    const button = element<HTMLButtonElement>(`speed-${speed}`);
    button.addEventListener("click", () => {
      playback.speed = speed;
      speedButtons.forEach((other) => other.classList.toggle("on", other === button));
    });
    button.classList.toggle("on", speed === playback.speed);
    return button;
  });
  window.addEventListener("keydown", (event) => {
    if (event.code === "Space") {
      event.preventDefault();
      playback.toggle(store.duration);
    }
  });
  if (params.get("autoplay") === "1") playback.toggle(store.duration);

  let last = performance.now();
  let drawn = 0;
  const frame = (now: number): void => {
    if (now - drawn >= FRAME_MILLISECONDS) {
      playback.advance((now - last) / 1000, store.duration, hurrying() ? DEAD_TIME_BOOST : 1);
      last = now;
      drawn = now;
      render();
    }
    requestAnimationFrame(frame);
  };
  render();
  requestAnimationFrame(frame);
  // Debug hook for checking the picture from the console or a test driver.
  Object.assign(window, { viewer: { store, playback, render } });
}

void start();
