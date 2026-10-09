import type { Pos } from "./events.ts";
import { teamOf, type ReplayMeta, type TeamSide } from "./meta.ts";
import { metres, toTeamFrame } from "./stats.ts";
import type { Frame, MatchStore } from "./store.ts";

/** What a map shows: one team (optionally one player) over a stretch of the match. */
export interface MapFilter {
  team: TeamSide;
  playerId: string | null;
  from: number;
  to: number;
}

export interface PassNode {
  id: string;
  x: number;
  y: number;
  count: number;
}

export interface PassEdge {
  from: string;
  to: string;
  count: number;
}

export interface PassLine {
  start: Pos;
  end: Pos;
  outcome: string;
  progressive: boolean;
}

export interface PassMapData {
  nodes: PassNode[];
  edges: PassEdge[];
  lines: PassLine[];
}

export interface ShotDot {
  at: Pos;
  xg: number;
  outcome: string;
  playerId: string | null;
}

export interface Grid {
  columns: number;
  rows: number;
  cells: number[];
  max: number;
}

export interface PressMapData {
  /** Average number of our players within pressing reach of the ball, by where the ball was. */
  pressure: Grid;
  /** Where we won the ball back: tackles won and interceptions. */
  wins: Pos[];
}

export interface AveragePosition {
  id: string;
  x: number;
  y: number;
}

/** A player within this far of the ball, while the other side has it, is pressing. */
const PRESS_REACH_M = 10;
/** Heat and press samples are taken from every this-many frames, which is plenty for a map. */
const SAMPLE_EVERY = 2;
export const GRID_COLUMNS = 12;
export const GRID_ROWS = 8;

function emptyGrid(): Grid {
  return { columns: GRID_COLUMNS, rows: GRID_ROWS, cells: new Array<number>(GRID_COLUMNS * GRID_ROWS).fill(0), max: 0 };
}

function addToGrid(grid: Grid, at: Pos, amount: number): void {
  const column = Math.min(grid.columns - 1, Math.max(0, Math.floor(at.x * grid.columns)));
  const row = Math.min(grid.rows - 1, Math.max(0, Math.floor(at.y * grid.rows)));
  const index = row * grid.columns + column;
  grid.cells[index] = (grid.cells[index] ?? 0) + amount;
  grid.max = Math.max(grid.max, grid.cells[index] ?? 0);
}

function framesBetween(frames: readonly Frame[], from: number, to: number): Frame[] {
  return frames.slice(Math.max(Math.floor(from), 0), Math.floor(to) + 1);
}

function wanted(filter: MapFilter, id: string | null, meta: ReplayMeta): boolean {
  if (id === null) return false;
  if (teamOf(meta, id) !== filter.team) return false;
  return filter.playerId === null || filter.playerId === id;
}

/** Passes in the window: lines for each, plus the network of who played to whom. */
export function passMap(store: MatchStore, meta: ReplayMeta, filter: MapFilter): PassMapData {
  const sums = new Map<string, { x: number; y: number; count: number }>();
  const edges = new Map<string, PassEdge>();
  const lines: PassLine[] = [];
  for (const event of store.log) {
    if (event.type !== "pass" || event.t < filter.from || event.t > filter.to || event.pos === null) continue;
    if (event.team !== filter.team) continue;
    const start = toTeamFrame(event.pos, filter.team, event.homeDir);
    const end = event.endPos === null ? null : toTeamFrame(event.endPos, filter.team, event.homeDir);
    if (wanted(filter, event.playerId, meta) && end !== null) {
      lines.push({ start, end, outcome: event.outcome ?? "", progressive: event.progressive });
    }
    if (event.playerId === null) continue;
    const node = sums.get(event.playerId) ?? { x: 0, y: 0, count: 0 };
    sums.set(event.playerId, { x: node.x + start.x, y: node.y + start.y, count: node.count + 1 });
    if (event.outcome === "complete" && event.targetId !== null) {
      const key = `${event.playerId}>${event.targetId}`;
      const edge = edges.get(key) ?? { from: event.playerId, to: event.targetId, count: 0 };
      edges.set(key, { ...edge, count: edge.count + 1 });
    }
  }
  const nodes = [...sums].map(([id, node]) => ({ id, x: node.x / node.count, y: node.y / node.count, count: node.count }));
  return { nodes, edges: [...edges.values()], lines };
}

export function shotMap(store: MatchStore, filter: MapFilter): ShotDot[] {
  const dots: ShotDot[] = [];
  for (const event of store.log) {
    if (event.type !== "shot" || event.t < filter.from || event.t > filter.to || event.pos === null) continue;
    if (event.team !== filter.team) continue;
    if (filter.playerId !== null && event.playerId !== filter.playerId) continue;
    dots.push({ at: toTeamFrame(event.pos, filter.team, event.homeDir), xg: event.xg, outcome: event.outcome ?? "", playerId: event.playerId });
  }
  return dots;
}

/** Where the team's players spent their time (a single player when the filter names one). */
export function heatMap(store: MatchStore, meta: ReplayMeta, filter: MapFilter): Grid {
  const grid = emptyGrid();
  framesBetween(store.frames, filter.from, filter.to).forEach((frame, index) => {
    if (index % SAMPLE_EVERY !== 0) return;
    for (const player of frame.players) {
      if (wanted(filter, player.player_id, meta)) addToGrid(grid, toTeamFrame(player, filter.team, frame.homeDir), 1);
    }
  });
  return grid;
}

/** How hard the team presses, by where the ball is, and where it wins the ball back. */
export function pressMap(store: MatchStore, meta: ReplayMeta, filter: MapFilter): PressMapData {
  const pressure = emptyGrid();
  const samples = emptyGrid();
  framesBetween(store.frames, filter.from, filter.to).forEach((frame, index) => {
    if (index % SAMPLE_EVERY !== 0 || frame.carrierId === null) return;
    const holder = teamOf(meta, frame.carrierId);
    if (holder === null || holder === filter.team) return;
    const ball = { x: frame.ballX, y: frame.ballY };
    const pressers = frame.players.filter(
      (player) => teamOf(meta, player.player_id) === filter.team && metres(player, ball) <= PRESS_REACH_M,
    ).length;
    const at = toTeamFrame(ball, filter.team, frame.homeDir);
    addToGrid(pressure, at, pressers);
    addToGrid(samples, at, 1);
  });
  pressure.max = 0;
  pressure.cells = pressure.cells.map((total, index) => {
    const count = samples.cells[index] ?? 0;
    const average = count === 0 ? 0 : total / count;
    pressure.max = Math.max(pressure.max, average);
    return average;
  });
  const wins: Pos[] = [];
  for (const event of store.log) {
    if (event.t < filter.from || event.t > filter.to || event.pos === null || event.team !== filter.team) continue;
    const won = event.type === "interception" || (event.type === "tackle" && event.outcome === "won");
    if (won) wins.push(toTeamFrame(event.pos, filter.team, event.homeDir));
  }
  return { pressure, wins };
}

/** Each player's average position over the window, in the team's frame. */
export function averagePositions(store: MatchStore, meta: ReplayMeta, filter: MapFilter): AveragePosition[] {
  const sums = new Map<string, { x: number; y: number; count: number }>();
  for (const frame of framesBetween(store.frames, filter.from, filter.to)) {
    for (const player of frame.players) {
      if (teamOf(meta, player.player_id) !== filter.team) continue;
      const at = toTeamFrame(player, filter.team, frame.homeDir);
      const sum = sums.get(player.player_id) ?? { x: 0, y: 0, count: 0 };
      sums.set(player.player_id, { x: sum.x + at.x, y: sum.y + at.y, count: sum.count + 1 });
    }
  }
  return [...sums].map(([id, sum]) => ({ id, x: sum.x / sum.count, y: sum.y / sum.count }));
}
