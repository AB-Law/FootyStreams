import { ZOOMS, cameraAt, toView, type Zoom } from "./camera.ts";
import { deadSpans, isDead } from "./deadtime.ts";
import { drawText } from "./font.ts";
import { drawOverlays, drawScoreboard } from "./hud.ts";
import { sampleAt } from "./interpolate.ts";
import { playerName, type ReplayMeta } from "./meta.ts";
import { activeFlight } from "./flights.ts";
import { overlaysAt } from "./overlays.ts";
import { posesAt } from "./poses.ts";
import { refereeTrack } from "./referee.ts";
import { pickKits } from "./palette.ts";
import { Playback, SPEEDS } from "./playback.ts";
import { WIDTH } from "./pitch.ts";
import { Panels } from "./panels.ts";
import { Scene } from "./scene.ts";
import { ScenePlayer } from "./sceneplay.ts";
import { NAME_MODES, SIDE_HEIGHT, SIDE_WIDTH, SideView, sideCameraX, type NameMode, type SideMode } from "./sideview.ts";
import { loadReplay } from "./source.ts";
import { StatsIndex, formatClock } from "./stats.ts";
import { MatchStore } from "./store.ts";

const FRAME_MILLISECONDS = 1000 / 30;
/** Below this width the side panels stack under the pitch; above it they flank it. */
const SIDE_BY_SIDE_FROM_PX = 1180;
const SIDE_PANELS_PX = 250 + 270 + 84;
const STAGE_PADDING_PX = 64;
const DEFAULT_REPLAY = "replays/replay";
const DEFAULT_ZOOM: Zoom = 2;
/** The canvas has twice the pixels of the logical 320 x 226 screen that the scoreboard and top-down view are drawn on. */
const PIXEL_RATIO = SIDE_WIDTH / WIDTH;
/** The page is shown at the largest scale that fits, in steps of a quarter so a window resize is not jumpy. */
const SCALE_STEP = 4;
/** Dead ball time (throw-ins, goal kicks, injuries) is played this much faster. */
const DEAD_TIME_BOOST = 3;

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`missing #${id}`);
  return found as T;
}

/** The largest scale that fits (in quarter steps, never below actual size), so pixels stay square and crisp. */
function fitCanvas(canvas: HTMLCanvasElement): void {
  const wide = window.innerWidth >= SIDE_BY_SIDE_FROM_PX;
  const room = wide ? window.innerWidth - SIDE_PANELS_PX : window.innerWidth - STAGE_PADDING_PX;
  const fit = Math.min(room / SIDE_WIDTH, (window.innerHeight - 140) / SIDE_HEIGHT);
  const scale = Math.max(1, Math.floor(fit * SCALE_STEP) / SCALE_STEP);
  canvas.style.width = `${SIDE_WIDTH * scale}px`;
  canvas.style.height = `${SIDE_HEIGHT * scale}px`;
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
  const sideView = new SideView(meta);
  const scenes = new ScenePlayer(store, meta);
  let view: "side" | "top" = params.get("view") === "top" ? "top" : "side";
  let names: NameMode = NAME_MODES.includes(params.get("names") as NameMode)
    ? (params.get("names") as NameMode)
    : "carrier";
  const kits = pickKits(meta);
  let focusId: string | null = null;
  const playback = new Playback();
  const panels = new Panels(store, meta, kits, new StatsIndex(store, meta), {
    seek: (seconds) => {
      playback.seek(seconds, store.duration);
      playback.playing = true;
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    follow: (id) => {
      focusId = id;
      status.textContent =
        id === null
          ? `${meta.home.name} v ${meta.away.name}`
          : `Following ${playerName(meta, id)} (click him again to release the camera)`;
    },
  });
  playback.seek(Number(params.get("t") ?? 0), store.duration);
  const scrubber = element<HTMLInputElement>("scrubber");
  const playButton = element<HTMLButtonElement>("play");
  const time = element<HTMLElement>("time");
  scrubber.max = String(Math.floor(store.duration));

  let zoom: Zoom = ZOOMS.includes(Number(params.get("zoom")) as Zoom)
    ? (Number(params.get("zoom")) as Zoom)
    : DEFAULT_ZOOM;
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

  const viewButton = element<HTMLButtonElement>("view");
  const labelZoomButtons = (): void => {
    const side = view === "side";
    element<HTMLButtonElement>("zoom-1").textContent = side ? "Wide" : "Full";
    element<HTMLButtonElement>("zoom-2").textContent = side ? "Broadcast" : "2x";
    element<HTMLButtonElement>("zoom-3").style.display = side ? "none" : "";
    element<HTMLButtonElement>("names").style.display = side ? "" : "none";
    viewButton.textContent = side ? "Top-down" : "Broadcast view";
  };
  viewButton.addEventListener("click", () => {
    view = view === "side" ? "top" : "side";
    labelZoomButtons();
    render();
  });
  labelZoomButtons();

  const namesButton = element<HTMLButtonElement>("names");
  const labelNames = (): void => {
    namesButton.textContent = `Names: ${names}`;
  };
  namesButton.addEventListener("click", () => {
    names = NAME_MODES[(NAME_MODES.indexOf(names) + 1) % NAME_MODES.length] ?? "carrier";
    labelNames();
    render();
  });
  labelNames();

  const debug: { locate: (playerId: string) => { x: number; y: number } | null; scenes: ScenePlayer } = {
    locate: () => null,
    scenes,
  };
  const render = (): void => {
    const sample = sampleAt(store.frames, playback.t);
    const overlays = overlaysAt(store.marks, playback.t, playback.speed);
    const referee = refereeTrack(store.frames, store.marks, playback.t);
    const extras = {
      t: playback.t,
      flight: activeFlight(store.flights, playback.t),
      referee: referee === null ? null : referee.spot,
      whistle: referee?.incident ?? false,
      big: false,
      poses: posesAt(store.contests, sample, playback.t, store.frames),
      focusId,
    };
    let locate: (playerId: string) => { x: number; y: number } | null;
    context.setTransform(1, 0, 0, 1, 0, 0);
    if (view === "side") {
      const mode: SideMode = zoom === 1 ? "wide" : "broadcast";
      const camX = sideCameraX(store.frames, playback.t, mode, focusId);
      sideView.draw(context, sample, extras, mode, camX, scenes.at(playback.t, sample), names);
      locate = (playerId) => {
        const at = sample === null ? null : sideView.locate(sample, mode, camX, playerId);
        return at === null ? null : { x: at.x / PIXEL_RATIO, y: at.y / PIXEL_RATIO };
      };
    } else {
      const camera = cameraAt(store.frames, playback.t, focusId !== null && zoom < 2 ? 2 : zoom, focusId);
      const ratio = PIXEL_RATIO * camera.zoom;
      context.setTransform(ratio, 0, 0, ratio, -camera.x * ratio, -camera.y * ratio);
      scene.draw(context, sample, { ...extras, big: camera.zoom > 1 });
      locate = (playerId) => {
        const world = sample === null ? null : scene.screenPosition(sample, playerId);
        return world === null ? null : toView(camera, world);
      };
    }
    context.setTransform(PIXEL_RATIO, 0, 0, PIXEL_RATIO, 0, 0);
    drawScoreboard(context, sample, meta, kits, playback.t >= store.duration);
    drawOverlays(context, overlays, meta, locate);
    if (hurrying()) drawText(context, ">>", WIDTH - 14, 24, "#ffd23f", 2);
    context.setTransform(1, 0, 0, 1, 0, 0);
    debug.locate = locate;
    scrubber.value = String(Math.floor(playback.t));
    playButton.textContent = playback.playing ? "Pause" : "Play";
    time.textContent = `${formatClock(playback.t)} / ${formatClock(store.duration)}`;
    panels.update(playback.t, performance.now());
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
  Object.assign(window, { viewer: { store, playback, render, debug } });
}

void start();
