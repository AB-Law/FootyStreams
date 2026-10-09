import { airTime, type IndexEntry } from "./channel.ts";
import type { CommentaryScript, MemoryNote } from "./commentary.ts";

// The side panels of the Channel page: the transcript of what is on, the lists of what is next and
// what has aired, what the hosts remember, and the control room.

function span(className: string, text: string): HTMLSpanElement {
  const node = document.createElement("span");
  node.className = className;
  node.textContent = text;
  return node;
}

/** One button per line of talk (or per card of a break); returns them in order so one can be marked. */
export function renderTranscript(list: HTMLElement, script: CommentaryScript, accentOf: (speakerId: string) => string): HTMLButtonElement[] {
  list.replaceChildren();
  const rows =
    script.lines.length > 0
      ? script.lines.map((line) => ({ who: line.speaker_name, say: line.text, colour: accentOf(line.speaker_id) }))
      : (script.slides ?? []).map((slide) => ({
          who: slide.kind === "ad" ? "Advert" : slide.kind === "breaking" ? "Breaking news" : slide.title,
          say: slide.kind === "ad" ? `${slide.title}: ${slide.lines[0] ?? ""}` : (slide.lines[0] ?? slide.rows.map((row) => row.label).join(", ")),
          colour: slide.accent,
        }));
  return rows.map((row) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.tabIndex = -1;
    button.style.setProperty("--who", row.colour);
    button.append(span("who", row.who), span("say", row.say));
    item.append(button);
    list.append(item);
    return button;
  });
}

export interface EntryList {
  entries: IndexEntry[];
  /** What to call each one: `title` for what is coming, `headline` for what has aired. */
  text: (entry: IndexEntry) => string;
  activeId?: string;
  onPick?: (entry: IndexEntry) => void;
}

/** The "up next" and "earlier" lists: air time, what kind of segment, and its title. */
export function renderEntries(list: HTMLElement, spec: EntryList): void {
  list.replaceChildren(
    ...spec.entries.map((entry) => {
      const item = document.createElement("li");
      const body = document.createElement(spec.onPick ? "button" : "div");
      if (body instanceof HTMLButtonElement) {
        body.type = "button";
        body.addEventListener("click", () => spec.onPick?.(entry));
      }
      body.className = entry.id === spec.activeId ? "entry on" : "entry";
      const title = document.createElement("b");
      title.textContent = spec.text(entry);
      body.append(span("when", airTime(entry.air_at)), span("kind", entry.guest ? "Interview" : entry.label || entry.kind), title);
      item.append(body);
      return item;
    }),
  );
}

export function renderMemories(list: HTMLElement, notes: MemoryNote[]): void {
  list.replaceChildren(
    ...notes.map((note) => {
      const item = document.createElement("li");
      const host = document.createElement("b");
      host.textContent = note.host;
      item.append(host, span("kind", ` ${note.kind.replace("_", " ")} `), document.createTextNode(note.text));
      return item;
    }),
  );
}

export interface ControlRoom {
  breakingForm: HTMLFormElement;
  breakingText: HTMLInputElement;
  guestForm: HTMLFormElement;
  guestText: HTMLInputElement;
  people: HTMLDataListElement;
  status: HTMLElement;
}

const TRIGGER_URL = "/api/trigger";
const NO_SERVER = "The viewer server cannot take requests: restart it (npm start), or use uv run channel breaking / guest.";

async function send(kind: "breaking" | "guest", text: string, status: HTMLElement): Promise<void> {
  status.textContent = "Sending…";
  try {
    const response = await fetch(TRIGGER_URL, {
      method: "POST",
      headers: { "content-type": "application/json", "x-vpl-trigger": "1" },
      body: JSON.stringify({ kind, text }),
    });
    if (response.ok) status.textContent = kind === "breaking" ? "Sent: it airs in a few seconds." : "Sent: they join after this segment.";
    else if (response.status === 404 || response.status === 405) status.textContent = NO_SERVER;
    else status.textContent = `Not sent: ${(await response.text()).slice(0, 120)}`;
  } catch {
    status.textContent = NO_SERVER;
  }
}

/** Wire the two forms to the server's trigger endpoint, and fill the guest suggestions from the directory. */
export function setupControlRoom(room: ControlRoom, feed: string): void {
  room.breakingForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = room.breakingText.value.trim();
    if (text !== "") void send("breaking", text, room.status).then(() => (room.breakingText.value = ""));
  });
  room.guestForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = room.guestText.value.trim();
    if (text !== "") void send("guest", text, room.status).then(() => (room.guestText.value = ""));
  });
  void fetch(`${feed}/directory.json`, { cache: "no-store" })
    .then(async (response) => (response.ok ? ((await response.json()) as { people?: { name: string; role: string; club: string }[] }) : null))
    .then((directory) => {
      for (const person of directory?.people ?? []) {
        const option = document.createElement("option");
        option.value = person.name;
        option.label = `${person.role}${person.club ? `, ${person.club}` : ""}`;
        room.people.append(option);
      }
    })
    .catch(() => undefined);
}
