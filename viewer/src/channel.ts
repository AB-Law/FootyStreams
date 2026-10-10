import type { CommentaryLine, CommentaryScript, Guest, MemoryNote, Screen, Slide } from "./commentary.ts";

// The 24/7 channel: `uv run channel` keeps a feed (index.json and one file per segment) and the page
// plays whatever the wall clock says is on air, joining in the middle like a real broadcast.

export interface HostRef {
  id: string;
  name: string;
}

export interface IndexEntry {
  id: string;
  file: string;
  kind: string;
  /** A spoiler-free teaser: a match report is listed by its fixture, not its score. */
  title: string;
  /** The real title, for the list of what has already aired. */
  headline: string;
  label: string;
  /** The guest's name, for an interview. */
  guest: string;
  /** Epoch seconds when the segment goes on air. */
  air_at: number;
  duration_s: number;
}

export interface ChannelIndex {
  channel: string;
  generated_at: number;
  cast: HostRef[];
  segments: IndexEntry[];
}

export type OnAir =
  | { state: "live"; entry: IndexEntry; t: number; next: IndexEntry | null }
  | { state: "standby"; next: IndexEntry | null };

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;
const text = (value: unknown, fallback = ""): string => (typeof value === "string" ? value : fallback);
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const strings = (value: unknown): string[] => list(value).filter((item): item is string => typeof item === "string");

function notesOf(value: unknown): MemoryNote[] {
  return list(value).flatMap((row) =>
    isRecord(row) && typeof row.text === "string" ? [{ host: text(row.host), kind: text(row.kind), text: row.text }] : [],
  );
}

function entryOf(row: unknown): IndexEntry | null {
  if (!isRecord(row) || typeof row.id !== "string" || typeof row.file !== "string") return null;
  if (typeof row.air_at !== "number" || typeof row.duration_s !== "number" || row.duration_s <= 0) return null;
  return {
    id: row.id,
    file: row.file,
    kind: text(row.kind),
    title: text(row.title),
    headline: text(row.headline, text(row.title)),
    label: text(row.label),
    guest: text(row.guest),
    air_at: row.air_at,
    duration_s: row.duration_s,
  };
}

/** The feed, checked: rows that are not usable are dropped, and a feed that is not a feed is null. */
export function parseIndex(data: unknown): ChannelIndex | null {
  if (!isRecord(data) || !Array.isArray(data.segments)) return null;
  const cast = list(data.cast).flatMap((row) => (isRecord(row) && typeof row.id === "string" ? [{ id: row.id, name: text(row.name, row.id) }] : []));
  const segments = data.segments.flatMap((row) => entryOf(row) ?? []).sort((a, b) => a.air_at - b.air_at);
  return {
    channel: text(data.channel, "VPL News"),
    generated_at: typeof data.generated_at === "number" ? data.generated_at : 0,
    cast,
    segments,
  };
}

/** What the wall clock says is on: the segment and how far into it, or stand by with what is next. */
export function onAir(index: ChannelIndex, now: number): OnAir {
  const at = index.segments.findIndex((entry) => entry.air_at <= now && now < entry.air_at + entry.duration_s);
  if (at >= 0) {
    const entry = index.segments[at]!;
    return { state: "live", entry, t: now - entry.air_at, next: index.segments[at + 1] ?? null };
  }
  return { state: "standby", next: index.segments.find((entry) => entry.air_at > now) ?? null };
}

/** What has aired, most recent first, for the "earlier" list. */
export function pastEntries(index: ChannelIndex, now: number): IndexEntry[] {
  return index.segments.filter((entry) => entry.air_at + entry.duration_s <= now).reverse();
}

/** The segment that follows `entry` in the schedule, if any. */
export function entryAfter(index: ChannelIndex, entry: IndexEntry): IndexEntry | null {
  const at = index.segments.findIndex((candidate) => candidate.id === entry.id);
  return at >= 0 ? (index.segments[at + 1] ?? null) : null;
}

/** The next few segments, soonest first. */
export function upcoming(index: ChannelIndex, now: number, limit: number): IndexEntry[] {
  return index.segments.filter((entry) => entry.air_at > now).slice(0, limit);
}

/** Seconds of airtime scheduled from `now` on. */
export function queuedSeconds(index: ChannelIndex, now: number): number {
  const end = Math.max(0, ...index.segments.map((entry) => entry.air_at + entry.duration_s));
  return Math.max(0, end - now);
}

function slidesOf(value: unknown): Slide[] {
  return list(value).flatMap((row) =>
    isRecord(row) && typeof row.kind === "string" && typeof row.seconds === "number" && row.seconds > 0
      ? [
          {
            kind: row.kind as Slide["kind"],
            title: text(row.title),
            lines: strings(row.lines),
            rows: list(row.rows).flatMap((item) => (isRecord(item) && typeof item.label === "string" ? [{ label: item.label, value: text(item.value) }] : [])),
            accent: text(row.accent, "#f2c200"),
            dark: text(row.dark, "#101418"),
            seconds: row.seconds,
          },
        ]
      : [],
  );
}

/** A segment file as a script the studio can play; null if it is not one. */
export function segmentScript(data: unknown): CommentaryScript | null {
  if (!isRecord(data) || !Array.isArray(data.lines)) return null;
  const slides = slidesOf(data.slides);
  const lines: CommentaryLine[] = data.lines.flatMap((row) =>
    isRecord(row) && typeof row.text === "string" && typeof row.duration_ms === "number"
      ? [{ speaker_id: text(row.speaker_id), speaker_name: text(row.speaker_name), text: row.text, duration_ms: row.duration_ms }]
      : [],
  );
  if (lines.length === 0 && slides.length === 0) return null;
  const screen = isRecord(data.screen) && Array.isArray(data.screen.rows) ? (data.screen as unknown as Screen) : null;
  const guest = isRecord(data.guest) && typeof data.guest.id === "string" ? (data.guest as unknown as Guest) : null;
  return {
    match_id: text(data.id),
    kind: text(data.kind) || undefined,
    label: text(data.label) || undefined,
    title: text(data.title),
    screen,
    guest,
    alert: text(data.alert) || undefined,
    slides,
    ticker: strings(data.ticker),
    memories: notesOf(data.memories),
    lines,
  };
}

/** `HH:MM` on the viewer's own clock. */
export function airTime(epochSeconds: number): string {
  const when = new Date(epochSeconds * 1000);
  return `${String(when.getHours()).padStart(2, "0")}:${String(when.getMinutes()).padStart(2, "0")}`;
}

/** `12 min` or `45 s`. */
export function howLong(seconds: number): string {
  return seconds >= 90 ? `${Math.round(seconds / 60)} min` : `${Math.round(seconds)} s`;
}
