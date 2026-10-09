import { CARRY_AHEAD_M, MOVE_SCRIPTS, playScript, touchTimes, type Foot, type Lying, type Script } from "./choreo.ts";
import { FEET_X, FEET_Y, FIGURE_H, FIGURE_HEIGHT_PX, FIGURE_W, STANCES, STRIDE_STEPS, blendJoints, figureFromJoints, figureSprite, gaitFor, swing, type FigureDress } from "./figure.ts";
import type { Kit } from "./palette.ts";
import { CHALLENGE_MODES, FREE_KICK_SCRIPT, failedMove, headerScript, tackleScript, type ChallengeMode } from "./scenes.ts";
import { SKILL_MOVES } from "./skillposes.ts";

const home: Kit = { pattern: "halves", primary: "#5d4037", secondary: "#f5deb3" };
const away: Kit = { pattern: "solid", primary: "#7a22b0", secondary: "#e8e8e8" };
const stripes: Kit = { pattern: "stripes", primary: "#c8102e", secondary: "#f5f5f5" };
const hoops: Kit = { pattern: "hoops", primary: "#0b3d91", secondary: "#f2c200" };
const sash: Kit = { pattern: "sash", primary: "#0b6b3c", secondary: "#f5f5f5" };
const look = { skin_tone: 5, hair_style: "short", hair_colour: "red", facial_hair: "none", build: "average" };

function dress(kit: Kit, appearance: Partial<typeof look> = {}, keeper: string | null = null): FigureDress {
  return { kit, keeper, appearance: { ...look, ...appearance } };
}

function section(title: string): HTMLElement {
  const holder = document.createElement("section");
  const heading = document.createElement("h2");
  heading.textContent = title;
  holder.append(heading);
  document.getElementById("sheet")?.append(holder);
  return holder;
}

function cell(parent: HTMLElement, label: string, width: number, height: number): CanvasRenderingContext2D {
  const wrap = document.createElement("figure");
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const caption = document.createElement("figcaption");
  caption.textContent = label;
  wrap.append(canvas, caption);
  parent.append(wrap);
  const ctx = canvas.getContext("2d");
  if (ctx === null) throw new Error("no canvas");
  ctx.imageSmoothingEnabled = false;
  return ctx;
}

/** Draw a sprite with its feet at (x, y), `scale` screen pixels per grid pixel, facing right or left, upright or lying. */
function stamp(ctx: CanvasRenderingContext2D, sprite: HTMLCanvasElement, x: number, y: number, scale: number, flip = false, lying: Lying | null = null): void {
  ctx.save();
  ctx.translate(x, y);
  if (lying !== null) ctx.translate(0, -5 * scale);
  if (flip) ctx.scale(-1, 1);
  if (lying === "forward") ctx.rotate(Math.PI / 2);
  if (lying === "slide") ctx.rotate(-Math.PI / 2);
  ctx.drawImage(sprite, -FEET_X * scale, -FEET_Y * scale, FIGURE_W * scale, FIGURE_H * scale);
  ctx.restore();
}

const SCALE = 6;
const BOX_W = 40 * SCALE;
const BOX_H = 50 * SCALE;
const GRASS = "#3f8f3f";

function grass(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.fillStyle = GRASS;
  ctx.fillRect(0, 0, width, height);
}

// ---- Static sheets ----

const cycle = section("Run cycle: eight frames, then the same figure running at stride speed");
for (let step = 0; step < STRIDE_STEPS; step++) {
  const ctx = cell(cycle, `frame ${step + 1}`, BOX_W, BOX_H);
  grass(ctx, BOX_W, BOX_H);
  stamp(ctx, figureSprite(dress(away), "run", step / STRIDE_STEPS, 1), BOX_W / 2, BOX_H - 24, SCALE);
}
const live = cell(cycle, "running (live)", BOX_W, BOX_H);

const heads = section("Heads, enlarged: hair styles, then facial hair, then skin tones");
function headCrop(label: string, figure: FigureDress): void {
  const ctx = cell(heads, label, 18 * 9, 18 * 9);
  grass(ctx, 18 * 9, 18 * 9);
  const sprite = figureSprite(figure, "stand", 0, 0);
  ctx.drawImage(sprite, 19, 14, 18, 18, 0, 0, 18 * 9, 18 * 9);
}
(["short", "buzz", "fade", "curly", "long", "braids", "bald"] as const).forEach((style) => headCrop(style, dress(away, { hair_style: style, hair_colour: "brown", skin_tone: 3 })));
(["none", "stubble", "goatee", "beard"] as const).forEach((facial) => headCrop(`face: ${facial}`, dress(away, { facial_hair: facial, hair_colour: "black", skin_tone: 4 })));
[1, 2, 3, 4, 5, 6, 7, 8].forEach((tone) => headCrop(`skin ${tone}`, dress(away, { skin_tone: tone, hair_colour: tone % 2 ? "black" : "blond" })));
(["black", "brown", "blond", "red", "grey"] as const).forEach((colour) => headCrop(`hair ${colour}`, dress(away, { hair_colour: colour, skin_tone: 2 })));

const kits = section("Kits and builds, standing: halves, solid, stripes, hoops, sash, keeper, referee");
const outfits: [string, FigureDress][] = [
  ["halves", dress(home, { skin_tone: 3, hair_colour: "black" })],
  ["solid", dress(away)],
  ["stripes", dress(stripes, { skin_tone: 1, hair_style: "long", hair_colour: "blond" })],
  ["hoops (stocky)", dress(hoops, { skin_tone: 4, hair_style: "bald", facial_hair: "beard", build: "stocky" })],
  ["sash (lean)", dress(sash, { skin_tone: 6, hair_style: "buzz", hair_colour: "black", build: "lean" })],
  ["keeper", dress({ pattern: "solid", primary: "#f5a623", secondary: "#222222" }, { skin_tone: 3, hair_colour: "brown" }, "#f5a623")],
  ["referee", dress({ pattern: "solid", primary: "#101114", secondary: "#f2d230" }, { skin_tone: 3, hair_colour: "black", build: "lean" })],
];
outfits.forEach(([label, figure]) => {
  const ctx = cell(kits, label, BOX_W, BOX_H);
  grass(ctx, BOX_W, BOX_H);
  stamp(ctx, figureSprite(figure, "stand", 0, 0), BOX_W / 2, BOX_H - 24, SCALE);
});

const gaitSection = section("Gaits on the spot, live: stand, walk, jog, run, sprint");
const gaitCells = [0, 1.2, 3, 5, 8].map((speed) => ({ speed, ctx: cell(gaitSection, `${speed} m/s`, BOX_W, BOX_H) }));

// ---- Scenes: skill moves, challenges, headers and a free kick ----

const attackerLook = dress(home, { skin_tone: 3, hair_colour: "black" });
const defenderLook = dress(away, { skin_tone: 2, hair_colour: "blond" });
const SKILL_SCALE = 3;
const PPM = (FIGURE_HEIGHT_PX / 1.8) * SKILL_SCALE;
const SCENE_H = 330;
const SCENE_W = 760;
const STRIP_W = 330;
const APPROACH_S = 0.7;
const TAIL_S = 0.9;

interface Setup {
  label: string;
  script: Script;
  /** The carrier's speed before and through the scene, in metres per second. */
  speed: number;
  /** Where the defender really is relative to the carrier when the scene starts, and how fast he closes. */
  defenderStart: number;
  closing: number;
  /** Three players in a line (a wall) instead of one defender. */
  wall: boolean;
  /** The ball sits still at the carrier's feet before the scene (a set piece) instead of being carried. */
  setPiece: boolean;
  /** Zoom out for wide scenes, live and in the frame strips. */
  zoomLive?: number;
  zoomStrip?: number;
}

function outcomeMode(outcome: string): ChallengeMode | null {
  return outcome === "tackled" ? "won" : outcome === "foul" ? "foul" : outcome === "lost" ? "lost" : null;
}

function setups(outcome: string, kind: "moves" | "tackles" | "other"): Setup[] {
  const run = { speed: 3.2, defenderStart: 3.3, closing: 0.6, wall: false, setPiece: false };
  if (kind === "moves") {
    const mode = outcomeMode(outcome);
    return SKILL_MOVES.map((move) => ({ ...run, label: `${move.replace("_", " ")}${mode === null ? "" : ` (${outcome})`}`, script: mode === null ? MOVE_SCRIPTS[move] : failedMove(move, mode) }));
  }
  if (kind === "tackles") return CHALLENGE_MODES.map((mode) => ({ ...run, label: `tackle: ${mode.replace("_", " ")}`, script: tackleScript(mode) }));
  const still = { speed: 0, defenderStart: 0.4, closing: 0, wall: false, setPiece: true };
  return [
    { ...still, label: "header: shot", script: headerScript("shot") },
    { ...still, label: "header: clearance", script: headerScript("clear") },
    { ...still, label: "free kick (wall jumps)", script: FREE_KICK_SCRIPT, defenderStart: 9.15, wall: true, zoomLive: 0.7, zoomStrip: 0.38 },
  ];
}

function drawBall(ctx: CanvasRenderingContext2D, x: number, y: number, lift: number, touching: boolean, k = 1): void {
  ctx.fillStyle = "rgba(0,0,0,0.3)";
  ctx.beginPath();
  ctx.ellipse(x, y, 13 * k, 4 * k, 0, 0, Math.PI * 2);
  ctx.fill();
  const top = y - 10 * k - lift;
  ctx.fillStyle = "#10141a";
  ctx.beginPath();
  ctx.arc(x, top, 11 * k, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(x, top, 9 * k, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#222";
  ctx.fillRect(x - 2 * k, top - 3 * k, 5 * k, 5 * k);
  if (touching) {
    ctx.strokeStyle = "#ffd23f";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, top, 18 * Math.max(k, 0.7), 0, Math.PI * 2);
    ctx.stroke();
  }
}

function drawScene(ctx: CanvasRenderingContext2D, setup: Setup, t: number, foot: Foot, width: number, strip: boolean): void {
  const k = (strip ? setup.zoomStrip : setup.zoomLive) ?? 1;
  const ppm = PPM * k;
  const sprite = SKILL_SCALE * k;
  const ground = SCENE_H - 100;
  const origin = (time: number): number => setup.speed * Math.min(time, APPROACH_S + setup.script.duration);
  const here = origin(t);
  ctx.fillStyle = GRASS;
  ctx.fillRect(0, 0, width, SCENE_H);
  ctx.fillStyle = "#388538";
  const stripe = ppm * 4;
  for (let n = -2; n < 24; n += 2) ctx.fillRect(n * stripe - ((here * ppm) % (2 * stripe)), 0, stripe, SCENE_H);
  const base = k < 1 ? (strip ? 95 : 200) : strip ? 80 : 190;
  const screenX = (f: number): number => base + (f - here) * ppm;
  const screenY = (l: number, h = 0): number => ground - l * ppm * 0.55 - h * ppm;
  const gait = gaitFor(setup.speed);
  const phase = t / gait.period;
  const s = t - APPROACH_S;
  const active = s >= 0;
  const run = swing(phase, gait.amp);
  const strideAmp = setup.script.body.some((key) => key.stance === "hips") ? 1 : gait.amp;
  const play = active ? playScript(setup.script, Math.min(s, setup.script.duration), phase, strideAmp, foot) : null;
  const done = s > setup.script.duration;
  const items: { y: number; draw: () => void }[] = [];
  const attackerF = here + (play?.attacker.f ?? 0);
  const attackerL = play?.attacker.l ?? 0;
  const attackerH = play?.attacker.h ?? 0;
  const attackerJoints = play === null ? (setup.speed === 0 ? STANCES.ready : run) : play.attacker.joints;
  items.push({
    y: screenY(attackerL),
    draw: () => stamp(ctx, figureFromJoints(attackerLook, attackerJoints), screenX(attackerF), screenY(attackerL, attackerH), sprite, play?.attacker.turn === true, play?.attacker.lying ?? null),
  });
  const realRel = setup.defenderStart - setup.closing * Math.max(s, 0);
  const copies = setup.wall ? [-0.9, 0, 0.9] : [0];
  copies.forEach((offset) => {
    const pull = play?.defender.w ?? 0;
    const stanceW = play?.defender.stanceW ?? 0;
    const relL = 0.25 + offset;
    const defF = here + realRel + pull * ((play?.defender.f ?? realRel) - realRel);
    const defL = relL + pull * ((play?.defender.l ?? relL) - relL);
    const defH = play?.defender.h ?? 0;
    const joints = play === null ? STANCES.jockey : blendJoints(STANCES.jockey, play.defender.joints, Math.max(stanceW, pull));
    const faces = setup.wall ? true : play?.defender.turn !== true;
    items.push({ y: screenY(defL), draw: () => stamp(ctx, figureFromJoints(defenderLook, joints), screenX(defF), screenY(defL, defH), sprite, faces, play?.defender.lying ?? null) });
  });
  const carriedBall = setup.setPiece ? { f: 0, l: 0, h: 0.11 } : { f: CARRY_AHEAD_M, l: 0, h: 0.11 };
  const ball = play === null ? carriedBall : play.ball;
  const settledOwner = done && play !== null ? play.owner : null;
  const ballF = settledOwner === "defender" ? here + realRel - CARRY_AHEAD_M : here + ball.f;
  const ballL = settledOwner === "defender" ? 0.25 : ball.l;
  items.push({ y: screenY(ballL) + 1, draw: () => drawBall(ctx, screenX(ballF), screenY(ballL), (ball.h - 0.11) * ppm, play?.touching != null, k) });
  items.sort((a, b) => a.y - b.y).forEach((item) => item.draw());
  if (strip) {
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(0, 0, 70, 16);
    ctx.fillStyle = "#fff";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(`${Math.max(s, 0).toFixed(2)} s`, 6, 12);
    return;
  }
  const loop = APPROACH_S + setup.script.duration + TAIL_S;
  ctx.fillStyle = "rgba(255,255,255,0.8)";
  ctx.fillRect(0, SCENE_H - 4, (width * (t % loop)) / loop, 4);
  touchTimes(setup.script).forEach((time) => {
    ctx.fillStyle = "#ffd23f";
    ctx.fillRect(((APPROACH_S + time) / loop) * width - 1, SCENE_H - 12, 3, 8);
  });
}

const controls = { outcome: "success", foot: "near" as Foot };
const sceneSections = [
  { key: "moves" as const, title: "Skill moves, live (choose the outcome and the foot above; rings mark each touch of the ball)" },
  { key: "tackles" as const, title: "Tackles, live: a firm tackle, a missed lunge, a foul, a slide that wins it, a slide that fouls, a heavy touch lost" },
  { key: "other" as const, title: "Headers and a free kick, live" },
];
let liveScenes: { setup: Setup; ctx: CanvasRenderingContext2D }[] = [];
const liveHolders = sceneSections.map((entry) => section(entry.title));
const stripHolders = sceneSections.map((entry) => section(`${entry.title.split(",")[0]}: frame by frame`));
const STRIP_TIMES = [0.15, 0.4, 0.65, 0.9, 1.2, 1.6];

function rebuild(): void {
  liveScenes = [];
  sceneSections.forEach((entry, index) => {
    const holder = liveHolders[index] as HTMLElement;
    const strips = stripHolders[index] as HTMLElement;
    holder.querySelectorAll("figure").forEach((node) => node.remove());
    strips.querySelectorAll("div").forEach((node) => node.remove());
    for (const setup of setups(controls.outcome, entry.key)) {
      liveScenes.push({ setup, ctx: cell(holder, setup.label, SCENE_W, SCENE_H) });
      const row = document.createElement("div");
      row.style.cssText = "display:flex;gap:2px;flex-basis:100%;align-items:flex-start";
      const label = document.createElement("div");
      label.textContent = setup.label;
      label.style.cssText = "width:90px;color:#8fa3b8;font-size:12px;padding-top:6px";
      row.append(label);
      strips.append(row);
      const times = setup.script.duration > 2.2 ? [0.3, 0.9, 1.5, 2.1, 2.6, 2.9, 3.3] : STRIP_TIMES.filter((time) => time <= setup.script.duration);
      times.forEach((time) => {
        const canvas = document.createElement("canvas");
        canvas.width = STRIP_W;
        canvas.height = SCENE_H;
        const ctx = canvas.getContext("2d");
        if (ctx === null) return;
        ctx.imageSmoothingEnabled = false;
        drawScene(ctx, setup, APPROACH_S + time, controls.foot, STRIP_W, true);
        row.append(canvas);
      });
    }
  });
}
rebuild();

let slow = 1;
let paused = false;
let clock = 0;
let last = performance.now();
document.getElementById("speed")?.addEventListener("input", (event) => {
  slow = Number((event.target as HTMLInputElement).value);
});
document.getElementById("pause")?.addEventListener("click", (event) => {
  paused = !paused;
  (event.target as HTMLButtonElement).textContent = paused ? "Play" : "Pause";
});
document.getElementById("restart")?.addEventListener("click", () => {
  clock = 0;
});
document.getElementById("outcome")?.addEventListener("change", (event) => {
  controls.outcome = (event.target as HTMLSelectElement).value;
  rebuild();
});
document.getElementById("foot")?.addEventListener("change", (event) => {
  controls.foot = (event.target as HTMLSelectElement).value as Foot;
  rebuild();
});

function frameLoop(now: number): void {
  if (!paused) clock += ((now - last) / 1000) * slow;
  last = now;
  live.fillStyle = GRASS;
  live.fillRect(0, 0, BOX_W, BOX_H);
  stamp(live, figureSprite(dress(away), "run", clock / 0.5, 1), BOX_W / 2, BOX_H - 24, SCALE);
  gaitCells.forEach(({ speed, ctx }) => {
    grass(ctx, BOX_W, BOX_H);
    const gait = gaitFor(speed);
    stamp(ctx, figureSprite(dress(home, { skin_tone: 3, hair_colour: "black" }), gait.pose, clock / gait.period, gait.amp), BOX_W / 2, BOX_H - 24, SCALE);
  });
  liveScenes.forEach(({ setup, ctx }) => {
    const loop = APPROACH_S + setup.script.duration + TAIL_S;
    drawScene(ctx, setup, clock % loop, controls.foot, SCENE_W, false);
  });
  requestAnimationFrame(frameLoop);
}
requestAnimationFrame(frameLoop);
