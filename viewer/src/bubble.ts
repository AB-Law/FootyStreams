import { wrapText } from "./pixelfont.ts";

// What a speech bubble says and when: a line of commentary is wrapped to the bubble, split into pages
// if it will not fit, and typed out at speaking pace. All of it is a pure function of the time, so
// scrubbing and replaying show the same thing.

export const BUBBLE_LINES = 4;
/** Speaking pace the typing follows, in characters a second (about 190 words a minute). */
const SPEECH_CPS = 16;
/** The text is all showing by this share of a line's time, so there is a beat left to read it. */
const TYPING_SHARE = 0.85;
/** Seconds a full page stays up before the next one starts typing. */
const PAGE_HOLD = 1;

/** Wrap `text` to `maxWidth` pixels and split it into pages of at most `maxLines`, evenly filled. */
export function paginate(text: string, maxWidth: number, maxLines = BUBBLE_LINES): string[][] {
  const lines = wrapText(text, maxWidth);
  if (lines.length === 0) return [];
  const pageCount = Math.ceil(lines.length / maxLines);
  const perPage = Math.ceil(lines.length / pageCount);
  return Array.from({ length: pageCount }, (_, page) => lines.slice(page * perPage, (page + 1) * perPage));
}

export interface Typed {
  page: number;
  pageCount: number;
  /** The page's lines in full; `shown` says how many characters of them are on screen. */
  lines: string[];
  shown: number;
  /** Mid-sentence, so the speaker's mouth moves. */
  speaking: boolean;
  /** Everything is on screen and nothing more is coming. */
  done: boolean;
}

const charCount = (page: string[]): number => page.reduce((sum, line) => sum + line.length, 0);

/** The bubble `elapsed` seconds into a line that lasts `duration` seconds. */
export function typedAt(pages: string[][], elapsed: number, duration: number): Typed {
  const counts = pages.map(charCount);
  const total = counts.reduce((sum, count) => sum + count, 0);
  const budget = Math.max(0.5, duration * TYPING_SHARE - PAGE_HOLD * Math.max(0, pages.length - 1));
  const rate = Math.max(SPEECH_CPS, total / budget);
  const last = pages.length - 1;
  let left = Math.max(0, elapsed);
  for (let page = 0; page < pages.length; page += 1) {
    const typing = (counts[page] ?? 0) / rate;
    const lines = pages[page] ?? [];
    if (left < typing) return { page, pageCount: pages.length, lines, shown: Math.floor(left * rate), speaking: true, done: false };
    left -= typing;
    if (page === last) break;
    if (left < PAGE_HOLD) return { page, pageCount: pages.length, lines, shown: counts[page] ?? 0, speaking: false, done: false };
    left -= PAGE_HOLD;
  }
  const lines = pages[last] ?? [];
  return { page: Math.max(last, 0), pageCount: pages.length, lines, shown: counts[last] ?? 0, speaking: false, done: true };
}
