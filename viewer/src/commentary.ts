/** Studio commentary script loaded beside a replay (from `uv run narrate`). */

export type Beat = "intro" | "club_colour" | "player_focus" | "wrap";

export interface CommentaryLine {
  speaker_id: string;
  speaker_name: string;
  text: string;
  /** Scripts from `uv run narrate` tag each line with a beat; channel segments tag the whole segment. */
  beat?: Beat;
  duration_ms: number;
}

/** What the right-hand wall screen shows: a score, a table or a fact card. */
export interface ScreenRow {
  label: string;
  value?: string;
}

export interface Screen {
  kind: "score" | "table" | "card";
  title: string;
  rows: ScreenRow[];
}

/** One card of a break: a sponsor, the table, the latest results, the next match, a breaking-news flash. */
export interface Slide {
  kind: "ad" | "table" | "results" | "fixture" | "breaking";
  title: string;
  lines: string[];
  rows: ScreenRow[];
  accent: string;
  dark: string;
  seconds: number;
}

/** A guest on the desk: a real person of the world, drawn from their own appearance and club colours. */
export interface Guest {
  id: string;
  name: string;
  kind: "player" | "manager";
  role: string;
  appearance: Record<string, string | number>;
  kit_primary: string;
  kit_secondary: string;
}

export interface MemoryNote {
  host: string;
  kind: string;
  text: string;
}

export interface CommentaryScript {
  match_id?: string;
  /** Channel segments: what kind of segment this is (talk, break, breaking). */
  kind?: string;
  /** A break has slides and no lines. */
  slides?: Slide[];
  guest?: Guest | null;
  /** The headline of a BREAKING NEWS segment: the banner stays up while it airs. */
  alert?: string;
  /** The ticker and what the hosts remember once this segment has aired (empty for a slotted-in one). */
  ticker?: string[];
  memories?: MemoryNote[];
  /** Channel segments: what the left screen says (a segment is one topic, unlike a narrate script). */
  label?: string;
  title?: string;
  screen?: Screen | null;
  lines: CommentaryLine[];
}

/** Cumulative start times (seconds) for each line; the last entry is total duration. */
export function lineStarts(script: CommentaryScript): number[] {
  const starts: number[] = [0];
  let t = 0;
  for (const line of script.lines) {
    t += Math.max(0.5, line.duration_ms / 1000);
    starts.push(t);
  }
  return starts;
}

/** The line being spoken at `t`, where it started and how long it has been going. After the end, the last line. */
export interface LineCue {
  line: CommentaryLine;
  index: number;
  start: number;
  duration: number;
  elapsed: number;
}

export function cueAt(script: CommentaryScript, t: number): LineCue | null {
  if (script.lines.length === 0) return null;
  const starts = lineStarts(script);
  let index = script.lines.findIndex((_, i) => t < (starts[i + 1] ?? 0));
  if (index < 0) index = script.lines.length - 1;
  const start = starts[index] ?? 0;
  const duration = (starts[index + 1] ?? start) - start;
  return { line: script.lines[index]!, index, start, duration, elapsed: Math.min(Math.max(t - start, 0), duration) };
}

export function lineAt(script: CommentaryScript, t: number): CommentaryLine | null {
  return cueAt(script, t)?.line ?? null;
}

export interface Speaker {
  id: string;
  name: string;
}

/** Everyone who speaks, in the order they first do. */
export function speakersOf(script: CommentaryScript): Speaker[] {
  const seen = new Map<string, Speaker>();
  for (const line of script.lines) {
    if (!seen.has(line.speaker_id)) seen.set(line.speaker_id, { id: line.speaker_id, name: line.speaker_name });
  }
  return [...seen.values()];
}

/** What the desk is on at each beat, for the wall screen. */
export const BEAT_LABELS: Record<Beat, string> = {
  intro: "Match report",
  club_colour: "The clubs",
  player_focus: "Player watch",
  wrap: "By the numbers",
};

/** The left-screen topic for the line being spoken: the segment's own, else the beat's, else the channel name. */
export function topicOf(script: CommentaryScript, line: CommentaryLine | null): string {
  return script.label ?? (line?.beat ? BEAT_LABELS[line.beat] : "VPL News");
}

export interface MatchResult {
  home: string;
  homeGoals: number;
  away: string;
  awayGoals: number;
}

const RESULT = /(\p{Lu}[\p{L}\p{M}0-9'’ -]*?)\s+(\d+)\s*,\s*(\p{Lu}[\p{L}\p{M}0-9'’ -]*?)\s+(\d+)/u;

/** The final score as the intro line states it ("Full time: Home 2, Away 1."), or null if it is not there. */
export function parseResult(script: CommentaryScript): MatchResult | null {
  const intro = script.lines.find((line) => line.beat === "intro")?.text ?? "";
  const found = RESULT.exec(intro);
  if (found === null) return null;
  return { home: found[1]!.trim(), homeGoals: Number(found[2]), away: found[3]!.trim(), awayGoals: Number(found[4]) };
}

export function scriptDuration(script: CommentaryScript): number {
  const starts = lineStarts(script);
  return starts[starts.length - 1] ?? 0;
}

export async function loadCommentary(path: string): Promise<CommentaryScript | null> {
  try {
    const response = await fetch(path);
    if (!response.ok) return null;
    const data = (await response.json()) as CommentaryScript;
    if (!Array.isArray(data.lines)) return null;
    return data;
  } catch {
    return null;
  }
}
