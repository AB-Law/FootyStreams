import { CARRY_AHEAD_M, MOVE_SECONDS, playMove, touchTimes } from "./choreo.ts";
import { FEET_X, FEET_Y, FIGURE_H, FIGURE_HEIGHT_PX, FIGURE_W, STANCES, STRIDE_STEPS, blendJoints, figureFromJoints, figureSprite, gaitFor, swing, type FigureDress } from "./figure.ts";
import type { Kit } from "./palette.ts";
import { SKILL_MOVES, type SkillMoveName } from "./skillposes.ts";

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
const skills = section("Skill moves, live: the ball is its own object and only moves where a boot touches it (rings mark each touch)");
const SKILL_W = 760;
const SKILL_H = 330;
const SKILL_SCALE = 3;
const PPM = (FIGURE_HEIGHT_PX / 1.8) * SKILL_SCALE;
const RUN_SPEED = 3.2;
const MOVE_START_S = 0.7;
const LOOP_S = MOVE_START_S + MOVE_SECONDS + 0.9;
const skillCells = SKILL_MOVES.map((move) => ({ move, ctx: cell(skills, move.replace("_", " "), SKILL_W, SKILL_H) }));
const attackerLook = dress(home, { skin_tone: 3, hair_colour: "black" });
const defenderLook = dress(away, { skin_tone: 2, hair_colour: "blond" });

function drawBall(ctx: CanvasRenderingContext2D, x: number, y: number, lift: number, touching: boolean): void {
  ctx.fillStyle = "rgba(0,0,0,0.3)";
  ctx.beginPath();
  ctx.ellipse(x, y, 13, 4, 0, 0, Math.PI * 2);
  ctx.fill();
  const top = y - 10 - lift;
  ctx.fillStyle = "#10141a";
  ctx.beginPath();
  ctx.arc(x, top, 11, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(x, top, 9, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#222";
  ctx.fillRect(x - 2, top - 3, 5, 5);
  if (touching) {
    ctx.strokeStyle = "#ffd23f";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, top, 18, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function drawSkill(ctx: CanvasRenderingContext2D, move: SkillMoveName, t: number, width = SKILL_W, strip = false): void {
  const ground = SKILL_H - 90;
  const origin = (time: number): number => RUN_SPEED * time;
  const here = origin(t);
  ctx.fillStyle = GRASS;
  ctx.fillRect(0, 0, width, SKILL_H);
  ctx.fillStyle = "#388538";
  const stripe = PPM * 4;
  for (let k = -2; k < 12; k += 2) ctx.fillRect(k * stripe - ((here * PPM) % (2 * stripe)) + 0, 0, stripe, SKILL_H);
  const screenX = (f: number): number => (strip ? 80 : 190) + (f - here) * PPM;
  const screenY = (l: number): number => ground - l * PPM * 0.55;
  const gait = gaitFor(RUN_SPEED);
  const phase = t / gait.period;
  const s = t - MOVE_START_S;
  const active = s >= 0 && s <= MOVE_SECONDS;
  const play = active ? playMove(move, s, phase, gait.amp) : null;
  // The defender walks toward him; the replay's own positions are what the move pulls him from.
  const realDefenderF = origin(MOVE_START_S) + 3.3 - 0.6 * (t - MOVE_START_S);
  const relF = realDefenderF - here;
  const relL = 0.25;
  const items: { y: number; draw: () => void }[] = [];
  const attackerF = here + (play === null ? 0 : play.attacker.f);
  const attackerL = play === null ? 0 : play.attacker.l;
  const attackerJoints = play === null ? swing(phase, gait.amp) : play.attacker.joints;
  items.push({
    y: screenY(attackerL),
    draw: () => stamp(ctx, figureFromJoints(attackerLook, attackerJoints), screenX(attackerF), screenY(attackerL), SKILL_SCALE, play?.attacker.turn === true),
  });
  const pull = play === null ? 0 : play.defender.w;
  const defF = here + relF + pull * ((play?.defender.f ?? relF) - relF);
  const defL = relL + pull * ((play?.defender.l ?? relL) - relL);
  const defJoints = play === null ? STANCES.jockey : blendJoints(STANCES.jockey, play.defender.joints, pull);
  items.push({
    y: screenY(defL),
    draw: () => stamp(ctx, figureFromJoints(defenderLook, defJoints), screenX(defF), screenY(defL), SKILL_SCALE, play?.defender.turn !== true),
  });
  const carried = { f: here + CARRY_AHEAD_M, l: 0, h: 0.11 };
  const ballPos = play === null ? carried : { f: here + play.ball.f, l: play.ball.l, h: play.ball.h };
  items.push({ y: screenY(ballPos.l) + 1, draw: () => drawBall(ctx, screenX(ballPos.f), screenY(ballPos.l), (ballPos.h - 0.11) * PPM, play?.touching != null) });
  items.sort((a, b) => a.y - b.y).forEach((item) => item.draw());
  if (strip) {
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(0, 0, 70, 16);
    ctx.fillStyle = "#fff";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(`${(t - MOVE_START_S).toFixed(2)} s`, 6, 12);
    return;
  }
  ctx.fillStyle = "rgba(255,255,255,0.8)";
  ctx.fillRect(0, SKILL_H - 4, (SKILL_W * (t % LOOP_S)) / LOOP_S, 4);
  touchTimes(move).forEach((time) => {
    ctx.fillStyle = "#ffd23f";
    ctx.fillRect(((MOVE_START_S + time) / LOOP_S) * SKILL_W - 1, SKILL_H - 12, 3, 8);
  });
}


// The same moves as still frames, so each position can be checked on its own.
const stripSection = section("Skill moves frame by frame (seconds into the move shown top-left; rings mark a boot on the ball)");
const STRIP_TIMES = [0.15, 0.4, 0.65, 0.9, 1.2, 1.6];
SKILL_MOVES.forEach((move) => {
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:2px;flex-basis:100%;align-items:flex-start";
  const label = document.createElement("div");
  label.textContent = move.replace("_", " ");
  label.style.cssText = "width:80px;color:#8fa3b8;font-size:12px;padding-top:6px";
  row.append(label);
  stripSection.append(row);
  STRIP_TIMES.forEach((time) => {
    const canvas = document.createElement("canvas");
    canvas.width = 330;
    canvas.height = SKILL_H;
    const ctx = canvas.getContext("2d");
    if (ctx === null) return;
    ctx.imageSmoothingEnabled = false;
    drawSkill(ctx, move, MOVE_START_S + time, 330, true);
    row.append(canvas);
  });
});

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
