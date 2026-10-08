import type { AnyEvent } from "./events.ts";
import type { ReplayMeta } from "./meta.ts";

/** Feed an NDJSON log (one event per line) to `onEvent`; blank lines are skipped. */
export function replayNdjson(text: string, onEvent: (event: AnyEvent) => void): void {
  for (const line of text.split("\n")) {
    if (line.trim() !== "") onEvent(JSON.parse(line) as AnyEvent);
  }
}

/** Fetch `<base>.ndjson` and `<base>.meta.json`, and feed the events to `onEvent`. */
export async function loadReplay(base: string, onEvent: (event: AnyEvent) => void): Promise<ReplayMeta> {
  const [log, meta] = await Promise.all([fetch(`${base}.ndjson`), fetch(`${base}.meta.json`)]);
  if (!log.ok || !meta.ok) throw new Error(`cannot load ${base}.ndjson / .meta.json (record one, see README)`);
  replayNdjson(await log.text(), onEvent);
  return (await meta.json()) as ReplayMeta;
}
