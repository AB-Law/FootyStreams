import { airTime, entryAfter, howLong, onAir, parseIndex, pastEntries, queuedSeconds, segmentScript, upcoming, type ChannelIndex, type IndexEntry } from "./channel.ts";
import { renderEntries, renderMemories, renderTranscript, setupControlRoom, type ControlRoom } from "./channel-panels.ts";
import { cueAt, scriptDuration, type CommentaryScript, type MemoryNote } from "./commentary.ts";
import { element, fit, injectStyles, reveal } from "./desk-page.ts";
import { drawShadowed, drawText, textWidth } from "./pixelfont.ts";
import { slideAt } from "./slides.ts";
import { Studio, type Notice } from "./studio.ts";
import { STUDIO_H, STUDIO_W } from "./studio-set.ts";

const FEED = "replays/channel";
const FRAME_MS = 1000 / 30;
const POLL_MS = 3000;
const UP_NEXT_SHOWN = 6;
const EARLIER_SHOWN = 40;
const DESK_LOOKBACK = 8;

const nowSeconds = (): number => Date.now() / 1000;
const clockSeconds = (): number => performance.now() / 1000;

interface PageParts {
  rec: HTMLElement;
  kind: HTMLElement;
  title: HTMLElement;
  queue: HTMLElement;
  lines: HTMLElement;
  side: HTMLElement;
  upNext: HTMLElement;
  earlier: HTMLElement;
  memories: HTMLElement;
  empty: HTMLElement;
  replayBar: HTMLElement;
  live: HTMLButtonElement;
  pause: HTMLButtonElement;
  scrub: HTMLInputElement;
  time: HTMLElement;
  room: ControlRoom;
}

/** A segment being watched again, from its start, until the viewer goes back to live. */
interface Replay {
  id: string;
  t: number;
  paused: boolean;
}

/** What is being shown: a segment, how far into it, and what follows. */
interface Shown {
  entry: IndexEntry;
  t: number;
  next: IndexEntry | null;
  replay: boolean;
}

/** The channel as the page sees it: the latest feed, the segments fetched so far, and the desk. */
class ChannelView {
  private index: ChannelIndex | null = null;
  private studio: Studio | null = null;
  private castKey = "";
  private tickerKey = "";
  private readonly scripts = new Map<string, CommentaryScript | null | "loading">();
  private airingId = "";
  private lineButtons: HTMLButtonElement[] = [];
  private shownLine = -1;
  private signatures = { upNext: "", earlier: "", memories: "", now: "" };
  private replay: Replay | null = null;
  private lastClock = clockSeconds();
  private readonly context: CanvasRenderingContext2D;
  private readonly dom: PageParts;

  constructor(context: CanvasRenderingContext2D, dom: PageParts) {
    this.context = context;
    this.dom = dom;
    dom.live.addEventListener("click", () => this.goLive());
    dom.pause.addEventListener("click", () => {
      if (this.replay !== null) this.replay.paused = !this.replay.paused;
    });
    dom.scrub.addEventListener("input", () => {
      if (this.replay !== null) this.replay.t = Number(this.dom.scrub.value);
    });
  }

  async poll(): Promise<void> {
    try {
      const response = await fetch(`${FEED}/index.json?${Date.now()}`, { cache: "no-store" });
      const parsed = response.ok ? parseIndex(await response.json()) : null;
      if (parsed !== null) this.accept(parsed);
    } catch {
      // The producer or server is away: keep playing what is already scheduled.
    }
    this.dom.empty.hidden = this.index !== null;
  }

  private accept(index: ChannelIndex): void {
    this.index = index;
    // Forget segments that have left the feed, or a channel left open for days grows without end.
    const listed = new Set(index.segments.map((entry) => entry.id));
    for (const id of this.scripts.keys()) if (!listed.has(id)) this.scripts.delete(id);
    const key = index.cast.map((host) => host.id).join(",");
    if (key !== this.castKey && index.cast.length > 0) {
      this.castKey = key;
      this.studio = new Studio(index.cast.map((host) => ({ id: host.id, name: host.name })));
      this.studio.setScript(null);
      this.airingId = "";
      this.tickerKey = "";
    }
  }

  private goLive(): void {
    this.replay = null;
    this.airingId = "";
  }

  private startReplay(entry: IndexEntry): void {
    this.replay = { id: entry.id, t: 0, paused: false };
    this.airingId = "";
    this.dom.side.scrollTo({ top: 0, behavior: "smooth" });
  }

  private load(entry: IndexEntry): CommentaryScript | null {
    const known = this.scripts.get(entry.id);
    if (known === "loading") return null;
    if (known !== undefined) return known;
    this.scripts.set(entry.id, "loading");
    void fetch(`${FEED}/${entry.file}`, { cache: "no-store" })
      .then(async (response) => (response.ok ? segmentScript(await response.json()) : null))
      .catch(() => null)
      .then((script) => {
        if (script === null) this.scripts.delete(entry.id);
        else this.scripts.set(entry.id, script);
      });
    return null;
  }

  /** What is being shown now: the replay if there is one (moving on through what aired), else what is on air. */
  private shown(index: ChannelIndex, now: number, dt: number): Shown | null {
    for (let guard = 0; this.replay !== null && guard < 3; guard += 1) {
      const replay = this.replay;
      const entry = index.segments.find((candidate) => candidate.id === replay.id);
      if (entry === undefined) break;
      if (!replay.paused && guard === 0) replay.t += dt;
      if (replay.t < entry.duration_s) return { entry, t: replay.t, next: entryAfter(index, entry), replay: true };
      const next = entryAfter(index, entry);
      this.replay = next !== null && next.air_at + next.duration_s <= now ? { id: next.id, t: 0, paused: false } : null;
    }
    this.replay = null;
    const live = onAir(index, now);
    return live.state === "live" ? { entry: live.entry, t: live.t, next: live.next, replay: false } : null;
  }

  private notice(shown: Shown | null, script: CommentaryScript | null): Notice | null {
    if (shown === null) return { label: "Stand by", detail: "Back shortly", silent: true };
    if (script === null) return { label: "Tuning in", silent: true };
    if (script.lines.length === 0 || shown.t < scriptDuration(script)) return null;
    return { label: "Up next", detail: shown.next?.title ?? "More from the desk", silent: true };
  }

  private standBy(index: ChannelIndex, now: number): Notice {
    const next = upcoming(index, now, 1)[0];
    return { label: "Stand by", detail: next ? `At ${airTime(next.air_at)}: ${next.label || next.title}` : "Back shortly", silent: true };
  }

  /** The ticker, or the memories, of the nearest segment at or before the one shown that has any. */
  private deskField<T>(index: ChannelIndex, anchorAt: number, pick: (script: CommentaryScript) => T[] | undefined): T[] {
    const candidates = index.segments.filter((entry) => entry.air_at <= anchorAt).reverse().slice(0, DESK_LOOKBACK);
    for (const entry of candidates) {
      const script = this.load(entry);
      const found = script === null ? undefined : pick(script);
      if (found !== undefined && found.length > 0) return found;
    }
    return [];
  }

  private renderDesk(index: ChannelIndex, anchorAt: number, studio: Studio): void {
    const ticker = this.deskField(index, anchorAt, (script) => script.ticker);
    const tickerKey = ticker.join("|");
    if (tickerKey !== this.tickerKey) {
      studio.setTicker(ticker);
      this.tickerKey = tickerKey;
    }
    const notes: MemoryNote[] = this.deskField(index, anchorAt, (script) => script.memories);
    const signature = notes.map((note) => `${note.host}${note.text}`).join("|");
    if (signature === this.signatures.memories) return;
    this.signatures.memories = signature;
    renderMemories(this.dom.memories, notes);
  }

  private renderLists(index: ChannelIndex, now: number): void {
    const coming = upcoming(index, now, UP_NEXT_SHOWN);
    const upNext = coming.map((entry) => `${entry.id}${entry.air_at}`).join("|");
    if (upNext !== this.signatures.upNext) {
      this.signatures.upNext = upNext;
      renderEntries(this.dom.upNext, { entries: coming, text: (entry) => entry.title });
    }
    const past = pastEntries(index, now).slice(0, EARLIER_SHOWN);
    const earlier = `${past.map((entry) => entry.id).join("|")}#${this.replay?.id ?? ""}`;
    if (earlier !== this.signatures.earlier) {
      this.signatures.earlier = earlier;
      renderEntries(this.dom.earlier, { entries: past, text: (entry) => entry.guest ? `${entry.guest}: ${entry.headline}` : entry.headline, activeId: this.replay?.id, onPick: (entry) => this.startReplay(entry) });
    }
  }

  private renderChrome(index: ChannelIndex, now: number, shown: Shown | null, script: CommentaryScript | null): void {
    const state = shown === null ? "standby" : shown.replay ? "replay" : "live";
    const title = shown === null ? "VPL News will be right back" : script?.title || (shown.replay ? shown.entry.headline : shown.entry.title);
    const signature = `${state}|${shown?.entry.id ?? ""}|${title}|${Math.round(queuedSeconds(index, now) / 10)}`;
    if (signature !== this.signatures.now) {
      this.signatures.now = signature;
      this.dom.rec.textContent = state === "live" ? "Live" : state === "replay" ? "Replay" : "Stand by";
      this.dom.rec.classList.toggle("paused", state !== "live");
      this.dom.kind.textContent = shown === null ? "Stand by" : (state === "replay" ? "Replay" : shown.entry.guest ? "Interview" : shown.entry.label || shown.entry.kind);
      this.dom.title.textContent = title;
      this.dom.queue.textContent = state === "replay" ? "Watching an earlier report" : `${howLong(queuedSeconds(index, now))} of airtime queued`;
    }
    this.dom.replayBar.hidden = this.replay === null;
    if (this.replay !== null && shown !== null) {
      this.dom.scrub.max = String(Math.floor(shown.entry.duration_s));
      this.dom.scrub.value = String(Math.floor(shown.t));
      this.dom.time.textContent = `${Math.floor(shown.t)} / ${Math.floor(shown.entry.duration_s)} s`;
      this.dom.pause.textContent = this.replay.paused ? "Play" : "Pause";
    }
  }

  /** Before the first feed arrives there is no desk to show: say what is being waited for. */
  private waiting(clock: number): void {
    const ctx = this.context;
    ctx.fillStyle = "#05090f";
    ctx.fillRect(0, 0, STUDIO_W, STUDIO_H);
    const title = "VPL NEWS";
    drawShadowed(ctx, title, Math.floor((STUDIO_W - textWidth(title, 3)) / 2), 104, "#f2c200", "#120c08", 3);
    const line = "WAITING FOR THE CHANNEL";
    drawText(ctx, `${line}${".".repeat(Math.floor(clock * 2) % 4)}`, Math.floor((STUDIO_W - textWidth(`${line}...`)) / 2), 150, "#8fa3b8");
  }

  frame(): void {
    const index = this.index;
    const studio = this.studio;
    const clock = clockSeconds();
    if (index === null || studio === null) {
      this.waiting(clock);
      return;
    }
    const now = nowSeconds();
    const dt = Math.min(clock - this.lastClock, 0.5);
    this.lastClock = clock;
    const shown = this.shown(index, now, dt);
    const script = shown === null ? null : this.load(shown.entry);
    if (shown?.next) this.load(shown.next);
    this.renderLists(index, now);
    this.renderChrome(index, now, shown, script);
    this.renderDesk(index, shown?.entry.air_at ?? now, studio);
    if (shown === null) {
      studio.setScript(null);
      this.airingId = "";
      studio.draw(this.context, 0, { clock, notice: this.standBy(index, now) });
      return;
    }
    if (script !== null && this.airingId !== shown.entry.id) {
      studio.setScript(script);
      this.lineButtons = renderTranscript(this.dom.lines, script, (id) => studio.accentOf(id));
      this.shownLine = -1;
      this.airingId = shown.entry.id;
    }
    if (script === null) studio.setScript(null);
    studio.draw(this.context, shown.t, { clock, notice: this.notice(shown, script), replay: shown.replay });
    this.markLine(script, shown.t);
  }

  private markLine(script: CommentaryScript | null, t: number): void {
    let index = -1;
    if (script !== null && script.lines.length > 0 && t < scriptDuration(script)) index = cueAt(script, t)?.index ?? -1;
    else if (script?.slides?.length) index = slideAt(script.slides, t).index;
    if (index === this.shownLine) return;
    this.lineButtons[this.shownLine]?.classList.remove("on");
    const active = this.lineButtons[index];
    active?.classList.add("on");
    if (active !== undefined) reveal(this.dom.side, active);
    this.shownLine = index;
  }
}

function start(): void {
  injectStyles();
  const canvas = element<HTMLCanvasElement>("screen");
  const stage = element<HTMLElement>("stage");
  const context = canvas.getContext("2d");
  if (context === null) throw new Error("no 2d canvas");
  context.imageSmoothingEnabled = false;
  fit(canvas, stage);
  window.addEventListener("resize", () => fit(canvas, stage));
  const room: ControlRoom = {
    breakingForm: element<HTMLFormElement>("breaking-form"),
    breakingText: element<HTMLInputElement>("breaking-text"),
    guestForm: element<HTMLFormElement>("guest-form"),
    guestText: element<HTMLInputElement>("guest-text"),
    people: element<HTMLDataListElement>("people"),
    status: element("control-status"),
  };
  setupControlRoom(room, FEED);
  const view = new ChannelView(context, {
    rec: element("rec"),
    kind: element("now-kind"),
    title: element("now-title"),
    queue: element("queue"),
    lines: element("lines"),
    side: element("side"),
    upNext: element("upnext"),
    earlier: element("earlier"),
    memories: element("memories"),
    empty: element("empty"),
    replayBar: element("replay-bar"),
    live: element<HTMLButtonElement>("go-live"),
    pause: element<HTMLButtonElement>("replay-pause"),
    scrub: element<HTMLInputElement>("replay-scrub"),
    time: element("replay-time"),
    room,
  });
  const poll = (): void => void view.poll().finally(() => window.setTimeout(poll, POLL_MS));
  poll();
  let drawn = 0;
  const frame = (now: number): void => {
    if (now - drawn >= FRAME_MS) {
      drawn = now;
      view.frame();
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

start();
