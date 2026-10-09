import { averagePositions, heatMap, passMap, pressMap, shotMap, type MapFilter } from "./analysis.ts";
import { drawHeatMap, drawPassLines, drawPassNetwork, drawPressMap, drawShape, drawShotMap, MAP_HEIGHT, MAP_WIDTH } from "./mapview.ts";
import { playerName, type ReplayMeta, type TeamSide } from "./meta.ts";
import type { Kit } from "./palette.ts";
import { MOMENTUM_WINDOW_S, formRating, type PlayerTally, type StatsIndex, type TeamStats } from "./stats.ts";
import type { MatchStore, Mark } from "./store.ts";

const SIDES: readonly TeamSide[] = ["home", "away"];
/** The DOM refreshes this often at most; the pitch itself draws at its own rate. */
const REFRESH_MS = 250;
const WINDOWS = [
  { label: "Whole match", seconds: Infinity },
  { label: "Last 15 min", seconds: 900 },
  { label: "Last 5 min", seconds: 300 },
] as const;

type MapKind = "network" | "passes" | "press" | "heat" | "shots" | "shape";
const MAPS: readonly { kind: MapKind; label: string }[] = [
  { kind: "network", label: "Pass network" },
  { kind: "passes", label: "Passes" },
  { kind: "press", label: "Press map" },
  { kind: "heat", label: "Heatmap" },
  { kind: "shots", label: "Shots" },
  { kind: "shape", label: "Shape" },
];

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className = "", text = ""): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className !== "") node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}

function percent(value: number): string {
  return `${Math.round(value * 100)}`;
}

function lastName(name: string): string {
  const parts = name.split(" ");
  return parts[parts.length - 1] ?? name;
}

/** One comparison row of the live statistics: label, both values and the home share of the bar. */
interface Row {
  label: string;
  home: string;
  away: string;
  share: number;
}

function ratio(home: number, away: number): number {
  const total = home + away;
  return total === 0 ? 0.5 : home / total;
}

function count(label: string, home: number, away: number, format: (value: number) => string = String): Row {
  return { label, home: format(home), away: format(away), share: ratio(home, away) };
}

function fraction(done: number, tried: number): string {
  return `${done}/${tried}`;
}

function accuracy(done: number, tried: number): string {
  return tried === 0 ? "-" : `${Math.round((100 * done) / tried)}%`;
}

function rows(home: TeamStats, away: TeamStats, momentum: number): Row[] {
  const pp = (value: number | null): string => (value === null ? "-" : value.toFixed(1));
  return [
    { label: "Possession", home: `${percent(home.possession)}%`, away: `${percent(away.possession)}%`, share: home.possession },
    { label: "Field tilt", home: `${percent(home.fieldTilt)}%`, away: `${percent(away.fieldTilt)}%`, share: home.fieldTilt },
    { label: "Momentum", home: `${percent(momentum)}%`, away: `${percent(1 - momentum)}%`, share: momentum },
    count("Expected goals", home.xg, away.xg, (value) => value.toFixed(2)),
    { label: "Shots (on target)", home: `${home.shots} (${home.onTarget})`, away: `${away.shots} (${away.onTarget})`, share: ratio(home.shots, away.shots) },
    count("Big chances", home.bigChances, away.bigChances),
    { label: "Passes (accuracy)", home: `${home.passes} (${accuracy(home.passesCompleted, home.passes)})`, away: `${away.passes} (${accuracy(away.passesCompleted, away.passes)})`, share: ratio(home.passes, away.passes) },
    count("Progressive passes", home.progressivePasses, away.progressivePasses),
    { label: "Dribbles won", home: fraction(home.dribblesWon, home.dribbles), away: fraction(away.dribblesWon, away.dribbles), share: ratio(home.dribblesWon, away.dribblesWon) },
    { label: "Tackles won", home: fraction(home.tacklesWon, home.tackles), away: fraction(away.tacklesWon, away.tackles), share: ratio(home.tacklesWon, away.tacklesWon) },
    count("Interceptions", home.interceptions, away.interceptions),
    count("Clearances", home.clearances, away.clearances),
    count("Saves", home.saves, away.saves),
    count("Fouls", home.fouls, away.fouls),
    count("Offsides", home.offsides, away.offsides),
    count("Corners", home.corners, away.corners),
    { label: "Cards (yellow, red)", home: `${home.yellows}, ${home.reds}`, away: `${away.yellows}, ${away.reds}`, share: ratio(home.yellows + 3 * home.reds, away.yellows + 3 * away.reds) },
    { label: "Press (opp. passes per action)", home: pp(home.ppda), away: pp(away.ppda), share: 0.5 },
    count("Distance (km)", home.distanceKm, away.distanceKm, (value) => value.toFixed(1)),
  ];
}

function prettyRole(role: string): string {
  return role.replace(/_/g, " ");
}

/** Everything beside the pitch: live statistics, lineups and the map drawer. */
export class Panels {
  private readonly store: MatchStore;
  private readonly meta: ReplayMeta;
  private readonly stats: StatsIndex;
  private readonly colours: Record<TeamSide, string>;
  private readonly statsBody: HTMLElement;
  private readonly lineupBody: HTMLElement;
  private readonly canvases: Record<TeamSide, HTMLCanvasElement>;
  private readonly titles: Record<TeamSide, HTMLElement>;
  private readonly playerSelect: HTMLSelectElement;
  private mapKind: MapKind = "network";
  private windowIndex = 0;
  private selected: { side: TeamSide; id: string } | null = null;
  private lastKey = "";
  private lastRefresh = 0;
  private time = 0;

  constructor(store: MatchStore, meta: ReplayMeta, kits: { home: Kit; away: Kit }, stats: StatsIndex) {
    this.store = store;
    this.meta = meta;
    this.stats = stats;
    this.colours = { home: kits.home.primary, away: kits.away.primary };
    this.statsBody = this.mount("stats", "Live stats");
    this.lineupBody = this.mount("lineups", "Lineups");
    const maps = document.getElementById("maps");
    if (maps === null) throw new Error("missing #maps");
    const canvases = el("div", "map-pair");
    this.canvases = { home: this.makeCanvas(), away: this.makeCanvas() };
    this.titles = { home: el("div", "map-title"), away: el("div", "map-title") };
    this.playerSelect = el("select");
    maps.append(this.controls(), canvases);
    for (const side of SIDES) {
      const holder = el("div", "map-holder");
      holder.append(this.titles[side], this.canvases[side]);
      canvases.append(holder);
    }
  }

  private mount(id: string, title: string): HTMLElement {
    const root = document.getElementById(id);
    if (root === null) throw new Error(`missing #${id}`);
    root.append(el("h2", "", title));
    const body = el("div", "body");
    root.append(body);
    return body;
  }

  private makeCanvas(): HTMLCanvasElement {
    const canvas = el("canvas", "map");
    canvas.width = MAP_WIDTH;
    canvas.height = MAP_HEIGHT;
    return canvas;
  }

  private controls(): HTMLElement {
    const bar = el("div", "map-controls");
    const tabs = el("div", "tabs");
    for (const map of MAPS) {
      const button = el("button", map.kind === this.mapKind ? "on" : "", map.label);
      button.addEventListener("click", () => {
        this.mapKind = map.kind;
        tabs.querySelectorAll("button").forEach((other) => other.classList.toggle("on", other === button));
        this.refresh(true);
      });
      tabs.append(button);
    }
    const windows = el("select");
    WINDOWS.forEach((window, index) => windows.append(new Option(window.label, String(index))));
    windows.addEventListener("change", () => {
      this.windowIndex = Number(windows.value);
      this.refresh(true);
    });
    this.fillPlayers();
    this.playerSelect.addEventListener("change", () => {
      const [side, id] = this.playerSelect.value.split("|");
      this.selected = id === undefined || id === "" ? null : { side: side as TeamSide, id };
      this.refresh(true);
    });
    bar.append(tabs, windows, this.playerSelect);
    return bar;
  }

  private fillPlayers(): void {
    this.playerSelect.append(new Option("All players", ""));
    for (const side of SIDES) {
      for (const [id, player] of Object.entries(this.meta[side].players)) {
        this.playerSelect.append(new Option(`${this.meta[side].short_code} ${player.number ?? ""} ${player.name}`, `${side}|${id}`));
      }
    }
  }

  /** Redraw the panels for replay time `t`; cheap to call every frame. */
  update(t: number, now: number): void {
    this.time = t;
    if (now - this.lastRefresh < REFRESH_MS) return;
    this.lastRefresh = now;
    this.refresh(false);
  }

  private refresh(force: boolean): void {
    const key = `${Math.floor(this.time)}|${this.mapKind}|${this.windowIndex}|${this.selected?.id ?? ""}`;
    if (!force && key === this.lastKey) return;
    this.lastKey = key;
    this.drawStats();
    this.drawLineups();
    this.drawMaps();
  }

  private drawStats(): void {
    const t = this.time;
    const all = this.stats.teamStats(0, t);
    const recent = this.stats.teamStats(Math.max(0, t - MOMENTUM_WINDOW_S), t);
    const body = this.statsBody;
    body.replaceChildren();
    const head = el("div", "stat-head");
    for (const side of SIDES) head.append(el("span", `side ${side}`, this.meta[side].short_code));
    body.append(head);
    for (const row of rows(all.home, all.away, recent.home.fieldTilt)) {
      const line = el("div", "stat");
      const values = el("div", "values");
      values.append(el("span", "", row.home), el("span", "label", row.label), el("span", "", row.away));
      const bar = el("div", "bar");
      const home = el("span");
      home.style.width = `${Math.round(row.share * 100)}%`;
      home.style.background = this.colours.home;
      const away = el("span");
      away.style.width = `${100 - Math.round(row.share * 100)}%`;
      away.style.background = this.colours.away;
      bar.append(home, away);
      line.append(values, bar);
      body.append(line);
    }
  }

  private onPitch(side: TeamSide): { slot: number; id: string; role: string; subbedOnAt: number | null }[] {
    const lineup = this.meta[side].lineup ?? [];
    const current = lineup.map((slot) => ({ slot: slot.slot, id: slot.player_id, role: slot.role, subbedOnAt: null as number | null }));
    for (const mark of this.store.marks as Mark[]) {
      if (mark.kind !== "substitution" || mark.t > this.time || mark.team !== side) continue;
      const entry = current.find((candidate) => candidate.id === mark.offId);
      if (entry !== undefined) {
        entry.id = mark.onId;
        entry.subbedOnAt = mark.t;
      }
    }
    return current;
  }

  private badges(id: string, tally: PlayerTally | undefined): string {
    const marks: string[] = [];
    if (tally !== undefined && tally.goals > 0) marks.push(`${tally.goals} G`);
    if (tally !== undefined && tally.assists > 0) marks.push(`${tally.assists} A`);
    for (const mark of this.store.marks) {
      if (mark.kind !== "card" || mark.t > this.time || mark.playerId !== id) continue;
      marks.push(mark.colour === "yellow" ? "YC" : "RC");
    }
    return marks.join(" ");
  }

  private drawLineups(): void {
    const tallies = this.stats.playerTallies(this.time);
    this.lineupBody.replaceChildren();
    for (const side of SIDES) {
      const team = this.meta[side];
      const block = el("div", "team");
      const title = el("div", "team-title");
      title.style.borderColor = this.colours[side];
      title.append(el("span", "", team.name), el("span", "formation", (team.formation ?? "").split("").join("-")));
      block.append(title);
      const players = this.onPitch(side);
      for (const entry of players) block.append(this.playerRow(side, entry.id, prettyRole(entry.role), tallies, entry.subbedOnAt !== null));
      const subsOn = new Set(players.filter((entry) => entry.subbedOnAt !== null).map((entry) => entry.id));
      const bench = (team.bench ?? []).filter((id) => !subsOn.has(id));
      if (bench.length > 0) {
        block.append(el("div", "bench-title", "Bench"));
        for (const id of bench) block.append(this.playerRow(side, id, "", tallies, false, true));
      }
      this.lineupBody.append(block);
    }
  }

  private playerRow(side: TeamSide, id: string, role: string, tallies: Map<string, PlayerTally>, subbedOn: boolean, benched = false): HTMLElement {
    const player = this.meta[side].players[id];
    const row = el("div", `player${this.selected?.id === id ? " selected" : ""}${benched ? " benched" : ""}`);
    const tally = tallies.get(id);
    row.append(el("span", "number", String(player?.number ?? "")), el("span", "name", player?.name ?? id));
    row.title = role;
    const badges = this.badges(id, tally);
    row.append(el("span", "badges", `${subbedOn ? "SUB " : ""}${badges}`.trim()));
    row.append(el("span", "rating", benched ? "" : formRating(tally).toFixed(1)));
    row.addEventListener("click", () => {
      this.selected = this.selected?.id === id ? null : { side, id };
      this.playerSelect.value = this.selected === null ? "" : `${side}|${id}`;
      this.refresh(true);
    });
    return row;
  }

  private filterFor(side: TeamSide): MapFilter {
    const span = WINDOWS[this.windowIndex]?.seconds ?? Infinity;
    const player = this.selected !== null && this.selected.side === side ? this.selected.id : null;
    return { team: side, playerId: player, from: Number.isFinite(span) ? Math.max(0, this.time - span) : 0, to: this.time };
  }

  private drawMaps(): void {
    for (const side of SIDES) {
      const canvas = this.canvases[side];
      const ctx = canvas.getContext("2d");
      if (ctx === null) continue;
      const filter = this.filterFor(side);
      const nameOf = (id: string): string => lastName(playerName(this.meta, id));
      const colour = this.colours[side];
      switch (this.mapKind) {
        case "network":
          drawPassNetwork(ctx, passMap(this.store, this.meta, filter), colour, nameOf);
          break;
        case "passes":
          drawPassLines(ctx, passMap(this.store, this.meta, filter));
          break;
        case "press":
          drawPressMap(ctx, pressMap(this.store, this.meta, filter), colour);
          break;
        case "heat":
          drawHeatMap(ctx, heatMap(this.store, this.meta, filter));
          break;
        case "shots":
          drawShotMap(ctx, shotMap(this.store, filter));
          break;
        case "shape":
          drawShape(ctx, averagePositions(this.store, this.meta, filter), colour, nameOf);
          break;
      }
      const who = filter.playerId === null ? this.meta[side].name : playerName(this.meta, filter.playerId);
      this.titles[side].textContent = `${who} - ${MAPS.find((map) => map.kind === this.mapKind)?.label ?? ""}`;
    }
  }
}
