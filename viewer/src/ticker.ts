import type { CommentaryScript, MatchResult } from "./commentary.ts";

const MAX_ITEM = 120;

/** The first sentence of `text`, cut at a word and ended with an ellipsis if it runs past `max`. */
export function firstSentence(text: string, max = MAX_ITEM): string {
  const sentence = (text.trim().split(/(?<=[.!?])\s/)[0] ?? "").trim();
  if (sentence.length <= max) return sentence;
  const cut = sentence.slice(0, max - 1);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 1)).trimEnd()}…`;
}

/** What scrolls along the bottom: the result, then the opening sentence of each line the desk reads. */
export function tickerItems(script: CommentaryScript, result: MatchResult | null): string[] {
  const items: string[] = [];
  if (result !== null) items.push(`${result.home} ${result.homeGoals}-${result.awayGoals} ${result.away}`);
  for (const line of script.lines) {
    if (line.beat === "intro") continue;
    const sentence = firstSentence(line.text);
    if (sentence !== "" && !items.includes(sentence)) items.push(sentence);
  }
  return items.length > 0 ? items : ["VPL News desk"];
}
