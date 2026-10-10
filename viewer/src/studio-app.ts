import { cueAt, lineStarts, loadCommentary, scriptDuration, speakersOf, topicOf, type CommentaryScript } from "./commentary.ts";
import { element, fit, injectStyles, reveal } from "./desk-page.ts";
import { Playback } from "./playback.ts";
import { formatClock } from "./stats.ts";
import { Studio } from "./studio.ts";

const FRAME_MS = 1000 / 30;
const DEFAULT_SCRIPT = "replays/commentary.json";

function buildTranscript(list: HTMLElement, script: CommentaryScript, studio: Studio, pick: (index: number) => void): HTMLButtonElement[] {
  return script.lines.map((line, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.style.setProperty("--who", studio.accentOf(line.speaker_id));
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = line.speaker_name;
    const topic = document.createElement("span");
    topic.className = "topic";
    topic.textContent = topicOf(script, line);
    who.append(topic);
    const say = document.createElement("span");
    say.className = "say";
    say.textContent = line.text;
    button.append(who, say);
    button.addEventListener("click", () => pick(index));
    item.append(button);
    list.append(item);
    return button;
  });
}

async function start(): Promise<void> {
  injectStyles();
  const params = new URLSearchParams(location.search);
  const canvas = element<HTMLCanvasElement>("screen");
  const stage = element<HTMLElement>("stage");
  const monitor = element<HTMLElement>("monitor");
  const empty = element<HTMLElement>("empty");
  const cover = element<HTMLButtonElement>("cover");
  const playButton = element<HTMLButtonElement>("play");
  const scrubber = element<HTMLInputElement>("scrubber");
  const time = element<HTMLElement>("time");
  const rec = element<HTMLElement>("rec");
  const context = canvas.getContext("2d");
  if (context === null) throw new Error("no 2d canvas");
  context.imageSmoothingEnabled = false;

  const script = await loadCommentary(params.get("script") ?? DEFAULT_SCRIPT);
  if (script === null || script.lines.length === 0) {
    monitor.hidden = true;
    element("controls").hidden = true;
    element("transcript").hidden = true;
    empty.hidden = false;
    return;
  }

  fit(canvas, stage);
  window.addEventListener("resize", () => fit(canvas, stage));
  const studio = new Studio(speakersOf(script));
  studio.setScript(script);
  const starts = lineStarts(script);
  const duration = scriptDuration(script);
  const playback = new Playback();
  scrubber.max = String(Math.floor(duration));
  playback.seek(Number(params.get("t") ?? 0), duration);

  const transcript = element("transcript");
  const seekLine = (index: number): void => {
    playback.seek(starts[Math.min(Math.max(index, 0), script.lines.length)] ?? 0, duration);
    render();
  };
  const buttons = buildTranscript(element("lines"), script, studio, (index) => {
    seekLine(index);
    if (!playback.playing) playback.toggle(duration);
  });

  let shownLine = -1;
  let shownSecond = -1;
  let shownPlaying: boolean | null = null;
  const render = (): void => {
    studio.draw(context, playback.t);
    const index = cueAt(script, playback.t)?.index ?? 0;
    if (index !== shownLine) {
      buttons[shownLine]?.classList.remove("on");
      buttons[index]?.classList.add("on");
      const active = buttons[index];
      if (active !== undefined) reveal(transcript, active);
      shownLine = index;
    }
    const second = Math.floor(playback.t);
    if (second !== shownSecond) {
      scrubber.value = String(second);
      time.textContent = `${formatClock(playback.t)} / ${formatClock(duration)}`;
      shownSecond = second;
    }
    if (playback.playing !== shownPlaying) {
      const atEnd = playback.t >= duration;
      playButton.textContent = playback.playing ? "Pause" : atEnd ? "Replay" : "Play";
      cover.textContent = atEnd ? "Replay" : "Play";
      cover.hidden = playback.playing;
      rec.classList.toggle("paused", !playback.playing);
      shownPlaying = playback.playing;
    }
  };

  const toggle = (): void => {
    playback.toggle(duration);
    render();
  };
  playButton.addEventListener("click", toggle);
  cover.addEventListener("click", toggle);
  canvas.addEventListener("click", toggle);
  element("prev").addEventListener("click", () => {
    const cue = cueAt(script, playback.t);
    seekLine(cue === null ? 0 : cue.elapsed > 1.5 ? cue.index : cue.index - 1);
  });
  element("next").addEventListener("click", () => seekLine((cueAt(script, playback.t)?.index ?? 0) + 1));
  scrubber.addEventListener("input", () => {
    playback.seek(Number(scrubber.value), duration);
    render();
  });
  window.addEventListener("keydown", (event) => {
    if (event.code === "Space" && !(event.target instanceof HTMLButtonElement)) {
      event.preventDefault();
      toggle();
    }
  });

  if (params.get("autoplay") === "1") playback.toggle(duration);
  let last = performance.now();
  let drawn = 0;
  const frame = (now: number): void => {
    if (now - drawn >= FRAME_MS) {
      playback.advance((now - last) / 1000, duration, 1);
      last = now;
      drawn = now;
      render();
    }
    requestAnimationFrame(frame);
  };
  render();
  requestAnimationFrame(frame);
}

void start();
