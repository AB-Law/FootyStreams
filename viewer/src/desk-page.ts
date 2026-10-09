import { STUDIO_H, STUDIO_W } from "./studio-set.ts";

// What the News desk and Channel pages share: the monitor frame styles, and fitting the canvas.

/** Pixels the monitor frame takes around the picture, side to side and top to bottom. */
const FRAME_X = 24;
const FRAME_Y = 150;

export function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`missing #${id}`);
  return found as T;
}

/** Whole-number scale where there is room for two or more (so pixels stay square), the exact fit below. */
function scaleFor(room: number): number {
  const raw = room / STUDIO_W;
  return raw >= 2 ? Math.floor(raw) : raw;
}

/** Size the canvas to its container, and tell the page how tall the stage is (CSS variables). */
export function fit(canvas: HTMLCanvasElement, stage: HTMLElement): void {
  const scale = scaleFor(Math.max(240, stage.clientWidth - FRAME_X));
  const [width, height] = [Math.floor(STUDIO_W * scale), Math.floor(STUDIO_H * scale)];
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  // Shrunk below its own size, smoothing keeps the small text legible; otherwise keep pixels sharp.
  canvas.style.imageRendering = scale < 1 ? "auto" : "pixelated";
  document.documentElement.style.setProperty("--stage-width", `${width + FRAME_X}px`);
  document.documentElement.style.setProperty("--stage-height", `${height + FRAME_Y}px`);
}

/** Keep the active line of a list in view without moving the page. */
export function reveal(container: HTMLElement, line: HTMLElement): void {
  const box = container.getBoundingClientRect();
  const at = line.getBoundingClientRect();
  if (at.top < box.top + 40 || at.bottom > box.bottom) container.scrollTop += at.top - box.top - box.height / 3;
}

const DESK_CSS = `
:root {
  color-scheme: dark;
  --bg: #070b10; --panel: #0f161e; --raised: #18222e; --edge: #263445;
  --muted: #8fa3b8; --ink: #f4f7fb; --gold: #f2c200; --red: #c8102e;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh;
  background: radial-gradient(1200px 600px at 50% -10%, #152033, var(--bg));
  color: var(--ink); font: 15px/1.45 "Segoe UI", "Helvetica Neue", sans-serif;
}
header {
  display: flex; gap: 16px; align-items: center; justify-content: space-between;
  padding: 12px 20px; border-bottom: 1px solid var(--edge); background: rgba(10, 14, 20, 0.85);
}
.brand { font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--gold); }
nav { display: flex; gap: 8px; }
nav a { color: var(--muted); text-decoration: none; border: 1px solid transparent; padding: 6px 12px; border-radius: 6px; }
nav a:hover { color: var(--ink); border-color: var(--edge); }
nav a.on { color: var(--ink); background: #243344; border-color: #3b5068; }
main {
  max-width: 1560px; margin: 0 auto; padding: 20px 16px 40px;
  display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-items: start;
}
@media (min-width: 1180px) {
  main { grid-template-columns: minmax(0, 1fr) 360px; }
  #transcript, #side { max-height: var(--stage-height, 70vh); }
}
#stage { display: grid; gap: 12px; min-width: 0; }
.monitor {
  justify-self: center; max-width: 100%; padding: 10px 12px 12px;
  background: linear-gradient(#141d29, #0b1119); border-radius: 18px;
  box-shadow: 0 0 0 1px var(--edge), inset 0 1px 0 #2b3b50, 0 24px 60px rgba(0, 0, 0, 0.55);
}
.monitor-bar {
  display: flex; justify-content: space-between; align-items: center; padding: 0 4px 8px;
  font: 600 11px/1 "Segoe UI", sans-serif; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted);
}
.rec { display: inline-flex; align-items: center; gap: 6px; color: #ff6b5e; }
.rec::before {
  content: ""; width: 8px; height: 8px; border-radius: 50%; background: #ff3b3b;
  box-shadow: 0 0 8px #ff3b3b; animation: pulse 1.6s ease-in-out infinite;
}
.rec.paused { color: var(--muted); }
.rec.paused::before { background: #5a6878; box-shadow: none; animation: none; }
@keyframes pulse { 50% { opacity: 0.35; } }
.glass { position: relative; border-radius: 10px; overflow: hidden; background: #000; box-shadow: inset 0 0 0 2px #05090f; }
canvas#screen { display: block; image-rendering: pixelated; background: #000; }
.glass::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(ellipse at center, transparent 62%, rgba(0, 0, 0, 0.38)),
    repeating-linear-gradient(to bottom, rgba(0, 0, 0, 0) 0, rgba(0, 0, 0, 0) 2px, rgba(0, 0, 0, 0.1) 3px);
}
#cover {
  position: absolute; left: 50%; top: 24%; transform: translate(-50%, -50%); z-index: 2;
  padding: 10px 24px; font: 700 15px/1 "Segoe UI", sans-serif; letter-spacing: 0.12em; text-transform: uppercase;
  color: #14161b; background: var(--gold); border: 0; border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.5), 0 10px 30px rgba(0, 0, 0, 0.5); cursor: pointer;
}
#cover:hover { background: #ffd83a; }
#cover[hidden] { display: none; }
#controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-self: center; width: 100%; max-width: var(--stage-width, 960px); }
button.tool { background: var(--raised); color: inherit; border: 1px solid #34465b; border-radius: 6px; padding: 7px 12px; font: inherit; cursor: pointer; }
button.tool:hover { background: #20303f; }
button.tool:focus-visible, #cover:focus-visible, .lines button:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
#scrubber { flex: 1; min-width: 100px; accent-color: var(--gold); }
#time { font-variant-numeric: tabular-nums; color: var(--muted); min-width: 8.5em; text-align: right; }
@media (max-width: 640px) {
  #cover { padding: 6px 16px; font-size: 12px; }
  #time { margin-left: auto; }
  #scrubber { order: 5; flex: 1 0 100%; }
  .monitor-bar { font-size: 9px; letter-spacing: 0.1em; }
}
#empty { padding: 28px; border: 1px dashed var(--edge); border-radius: 12px; color: var(--muted); }
#empty code { display: block; margin-top: 10px; padding: 10px 12px; background: #0a1017; border-radius: 6px; color: var(--ink); overflow-x: auto; }
#transcript, #side { background: var(--panel); border-radius: 14px; box-shadow: 0 0 0 1px var(--edge); overflow: hidden auto; }
#side { display: grid; align-content: start; }
.panel + .panel { border-top: 1px solid var(--edge); }
h2.panel-title {
  margin: 0; padding: 12px 14px; font: 700 11px/1 "Segoe UI", sans-serif; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--edge); position: sticky; top: 0; background: var(--panel); z-index: 1;
}
.lines { list-style: none; margin: 0; padding: 6px; display: grid; gap: 4px; }
.lines button {
  display: grid; gap: 2px; width: 100%; text-align: left; padding: 8px 10px 9px 12px; font: inherit; color: var(--muted);
  background: transparent; border: 0; border-left: 4px solid var(--who, var(--edge)); border-radius: 6px; cursor: pointer;
}
.lines button:hover { background: #141d28; }
.lines button.on { color: var(--ink); background: #1b2736; }
.lines.plain button { cursor: default; }
.lines .who { font: 700 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink); }
.lines .topic { font-weight: 400; color: var(--muted); margin-left: 6px; }
.lines .say { font-size: 14px; }
#nowbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-self: center; width: 100%; max-width: var(--stage-width, 960px); }
.pill { font: 700 11px/1 "Segoe UI", sans-serif; letter-spacing: 0.12em; text-transform: uppercase; color: #14161b; background: var(--gold); padding: 5px 9px; border-radius: 999px; }
#now-title { font-weight: 600; }
.muted { color: var(--muted); font-size: 13px; }
.rows { list-style: none; margin: 0; padding: 6px 14px 10px; display: grid; gap: 8px; }
.rows li { font-size: 14px; color: var(--muted); }
.rows b { color: var(--ink); font-weight: 600; }
.rows .when { font-variant-numeric: tabular-nums; color: var(--gold); margin-right: 8px; }
.rows .kind { font: 700 10px/1 "Segoe UI", sans-serif; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin-right: 6px; }
.rows .entry { display: block; width: 100%; text-align: left; background: transparent; border: 0; color: var(--muted); font: inherit; padding: 2px 0; }
.rows button.entry { cursor: pointer; border-radius: 6px; padding: 4px 6px; margin: 0 -6px; width: calc(100% + 12px); }
.rows button.entry:hover { background: #141d28; }
.rows .entry.on { background: #1b2736; }
#earlier { max-height: 320px; overflow-y: auto; }
.replay-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-self: center; width: 100%; max-width: var(--stage-width, 960px); }
.replay-bar[hidden] { display: none; }
.replay-bar input[type=range] { flex: 1; min-width: 100px; accent-color: var(--gold); }
button.tool.live { background: var(--gold); color: #14161b; font-weight: 700; border-color: var(--gold); }
button.tool.live:hover { background: #ffd83a; }
.control { display: grid; gap: 6px; padding: 12px 14px 4px; }
.control label { font: 700 11px/1 "Segoe UI", sans-serif; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
.control .row { display: flex; gap: 6px; }
.control input { flex: 1; min-width: 0; background: #0a1017; color: var(--ink); border: 1px solid #34465b; border-radius: 6px; padding: 7px 9px; font: inherit; }
.control input:focus-visible { outline: 2px solid var(--gold); outline-offset: 1px; }
#control-status { margin: 0; padding: 6px 14px 14px; min-height: 2.4em; }
`;

/** Add the page styles; called once as the page script starts. */
export function injectStyles(): void {
  const style = document.createElement("style");
  style.textContent = DESK_CSS;
  document.head.append(style);
}
