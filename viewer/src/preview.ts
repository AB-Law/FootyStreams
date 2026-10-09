import { FEET_X, FEET_Y, FIGURE_H, FIGURE_W, STRIDE_STEPS, figureSprite, gaitFor, type FigureDress, type FigurePose } from "./figure.ts";
import type { Kit } from "./palette.ts";
import { SKILL_MOVES, SKILL_MOVE_S, skillFrame, type SkillMoveName } from "./skillposes.ts";

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

/** Draw a sprite with its feet at (x, y), `scale` screen pixels per grid pixel, facing right or left. */
function stamp(ctx: CanvasRenderingContext2D, sprite: HTMLCanvasElement, x: number, y: number, scale: number, flip = false): void {
  ctx.save();
  ctx.translate(x, y);
  if (flip) ctx.scale(-1, 1);
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

// Run cycle: eight still frames, and one that runs.
const cycle = section("Run cycle: eight frames, then the same figure running at stride speed");
for (let step = 0; step < STRIDE_STEPS; step++) {
  const ctx = cell(cycle, `frame ${step + 1}`, BOX_W, BOX_H);
  grass(ctx, BOX_W, BOX_H);
  stamp(ctx, figureSprite(dress(away), "run", step / STRIDE_STEPS, 1), BOX_W / 2, BOX_H - 24, SCALE);
}
const live = cell(cycle, "running (live)", BOX_W, BOX_H);

// Heads: hair and facial hair at large size, so they can be compared.
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

// Kits and builds.
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

// Gaits, animated: a figure at each speed running on the spot.
const gaitSection = section("Gaits on the spot, live: stand, walk, jog, run, sprint");
const gaitCells = [0, 1.2, 3, 5, 8].map((speed) => ({ speed, ctx: cell(gaitSection, `${speed} m/s`, BOX_W, BOX_H) }));

// Skill moves, animated: attacker (halves kit) beats a defender (purple) with each move.
const skills = section("Skill moves, live: the attacker takes on a defender with each move (slow with the slider)");
const SKILL_W = 560;
const SKILL_H = 230;
const SKILL_SCALE = 2;
const PIXELS_PER_METRE = (FIGURE_HEIGHT_FOR_PREVIEW() * SKILL_SCALE) / 1.8;
function FIGURE_HEIGHT_FOR_PREVIEW(): number {
  return 31;
}
const TOP_DOWN_PPM = 300 / 105;
const LOOP_S = 4.2;
const MOVE_START_S = 1.2;
const skillCells = SKILL_MOVES.map((move) => ({ move, ctx: cell(skills, move.replace("_", " "), SKILL_W, SKILL_H) }));

function figurePose(profile: string): FigurePose {
  if (profile === "feint" || profile === "kick" || profile === "flick" || profile === "lean" || profile === "stand") return profile;
  return "run";
}

function drawBall(ctx: CanvasRenderingContext2D, x: number, y: number, lift: number): void {
  ctx.fillStyle = "rgba(0,0,0,0.3)";
  ctx.beginPath();
  ctx.ellipse(x, y, 9, 3, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#10141a";
  ctx.beginPath();
  ctx.arc(x, y - 7 - lift, 7.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(x, y - 7 - lift, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#222";
  ctx.fillRect(x - 1, y - 9 - lift, 3, 3);
}

function drawSkill(ctx: CanvasRenderingContext2D, move: SkillMoveName, t: number): void {
  ctx.fillStyle = GRASS;
  ctx.fillRect(0, 0, SKILL_W, SKILL_H);
  ctx.fillStyle = "#388538";
  for (let band = 0; band < 8; band += 2) ctx.fillRect(band * 70, 0, 70, SKILL_H);
  const ground = SKILL_H - 84;
  const speed = 3;
  const gait = gaitFor(speed);
  const baseX = 40 + speed * PIXELS_PER_METRE * t;
  const progress = (t - MOVE_START_S) / SKILL_MOVE_S;
  const active = progress >= 0 && progress < 1;
  const frame = active ? skillFrame(move, progress) : null;
  const toPx = (topDown: number): number => (topDown / TOP_DOWN_PPM) * PIXELS_PER_METRE;
  const attackerX = baseX + (frame === null ? 0 : toPx(frame.along));
  const attackerY = ground + (frame === null ? 0 : toPx(frame.across));
  const phase = t / gait.period;
  let pose: FigurePose = gait.pose;
  let amp = gait.amp;
  if (frame !== null) {
    pose = figurePose(frame.profile);
    amp = pose === "run" || pose === "lean" ? 1 : 0;
  }
  // The defender comes to meet the ball, lunges as the move starts, and is left standing.
  const meetX = 40 + speed * PIXELS_PER_METRE * (MOVE_START_S + SKILL_MOVE_S * 0.45) + 70;
  const defenderX = t < MOVE_START_S + 0.5 ? 470 - (470 - meetX) * Math.min(t / (MOVE_START_S + 0.5), 1) : meetX + (active && progress > 0.5 ? toPx(6) * Math.min((progress - 0.5) * 3, 1) : 0);
  const defenderPose: FigurePose = active && progress > 0.25 && progress < 0.65 ? "kick" : t < MOVE_START_S ? "run" : "stand";
  const defenderY = ground + 40;
  const past = baseX > defenderX + 10;
  const sprites: { y: number; draw: () => void }[] = [
    {
      y: attackerY,
      draw: () => stamp(ctx, figureSprite(dress(home, { skin_tone: 3, hair_colour: "black" }), pose, phase, amp), attackerX, attackerY, SKILL_SCALE, frame?.turn === -1),
    },
    {
      y: defenderY,
      draw: () => stamp(ctx, figureSprite(dress(away, { skin_tone: 2, hair_colour: "blond" }), defenderPose, t / 0.55, 0.8), defenderX, defenderY, SKILL_SCALE, !past),
    },
  ];
  const ballX = attackerX + 26 + (frame === null ? 0 : toPx(frame.ballAlong));
  const ballY = attackerY + (frame === null ? 0 : toPx(frame.ballAcross));
  sprites.push({ y: ballY + 1, draw: () => drawBall(ctx, ballX, ballY, frame === null ? 0 : toPx(frame.ballLift) * 1.2) });
  sprites.sort((a, b) => a.y - b.y).forEach((item) => item.draw());
  ctx.fillStyle = "rgba(255,255,255,0.8)";
  ctx.fillRect(0, SKILL_H - 4, (SKILL_W * (t % LOOP_S)) / LOOP_S, 4);
}

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
  skillCells.forEach(({ move, ctx }) => drawSkill(ctx, move, clock % LOOP_S));
  requestAnimationFrame(frameLoop);
}
requestAnimationFrame(frameLoop);

void FIGURE_H;
