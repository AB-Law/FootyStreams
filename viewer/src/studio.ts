import { anchorSprite } from "./anchor.ts";
import { castLooks, guestLook, type AnchorFace, type AnchorLook } from "./anchor-look.ts";
import { paginate, typedAt } from "./bubble.ts";
import { cueAt, parseResult, topicOf, type CommentaryScript, type MatchResult, type Speaker } from "./commentary.ts";
import { drawSlides } from "./slides.ts";
import { drawBreakingBanner, drawBubble, drawLowerThird, drawTicker, layoutTicker, TEXT_W, type TickerLayout } from "./studio-hud.ts";
import { drawBug, drawOnAir, drawRightScreen, drawTopicScreen, type Topic } from "./studio-screens.ts";
import { DESK_TOP, drawMic, drawTally, lightCone, paintBackdrop, paintDesk, paintDeskProps, STUDIO_H, STUDIO_W } from "./studio-set.ts";
import { tickerItems } from "./ticker.ts";

const MAX_SEATS = 4;
const SEAT_COLUMNS: Record<number, readonly number[]> = { 1: [240], 2: [160, 320], 3: [120, 240, 360], 4: [90, 190, 290, 390] };
/** Row of the screen where the top of each anchor's sprite goes. */
const SPRITE_TOP = 142;
const SPRITE_HALF = 32;
const MOUTH_CYCLE = [2, 0, 3, 1, 2, 3, 0, 2, 1, 3, 2, 0] as const;
const SLIDE_SECONDS = 0.4;
const STAND_BY = ["VPL News: the Valmere Premier League, 24 hours a day"];

interface Seat {
  speakerId: string;
  name: string;
  x: number;
  look: AnchorLook;
  /** The colour their lower third and tally light use. */
  accent: string;
  /** What the lower third says under a guest's name; hosts show the segment's topic instead. */
  role?: string;
}

/** The guest's chair, at the end of the desk. */
const GUEST_X = 440;

/** Something to say on the left screen instead of the topic, with the talk paused: "up next", "stand by". */
export interface Notice extends Topic {
  /** Hide the bubble and lower third, leaving the hosts idle. */
  silent?: boolean;
}

export interface FrameOptions {
  /** Seconds on a clock that never rewinds, for the ticker and the hosts' idle movement. Defaults to `t`. */
  clock?: number;
  notice?: Notice | null;
  /** Watching something again: the corner tag says REPLAY, not LIVE. */
  replay?: boolean;
}

function layer(): CanvasRenderingContext2D {
  const canvas = document.createElement("canvas");
  canvas.width = STUDIO_W;
  canvas.height = STUDIO_H;
  const ctx = canvas.getContext("2d");
  if (ctx === null) throw new Error("no 2d canvas");
  return ctx;
}

/** What is known about the script on air, worked out once when it is set. */
interface Airing {
  script: CommentaryScript;
  pages: string[][][];
  rows: number[];
  result: MatchResult | null;
}

/** The VPL News desk: anchors seated at a desk, with speech bubbles, lower third and ticker over them. */
export class Studio {
  private readonly seats: Seat[];
  private readonly back: HTMLCanvasElement;
  private readonly front: HTMLCanvasElement;
  private airing: Airing | null = null;
  private guestSeat: Seat | null = null;
  private ticker: TickerLayout = layoutTicker(STAND_BY);
  private tickerFixed = false;

  /** `cast` sits at the desk in order (up to four); the same people stay in the same seats for good. */
  constructor(cast: Speaker[]) {
    const speakers = cast.slice(0, MAX_SEATS);
    const columns = SEAT_COLUMNS[Math.max(speakers.length, 1)] ?? SEAT_COLUMNS[MAX_SEATS]!;
    const looks = castLooks(speakers.map((speaker) => speaker.id));
    this.seats = speakers.map((speaker, index) => ({ speakerId: speaker.id, name: speaker.name, x: columns[index]!, look: looks[index]!, accent: looks[index]!.accent }));
    const back = layer();
    paintBackdrop(back);
    const front = layer();
    paintDesk(front);
    paintDeskProps(front, this.seats.map((seat) => seat.x));
    this.back = back.canvas;
    this.front = front.canvas;
  }

  /** Put a script on air (or none: the desk waits). Resets the ticker unless it was set by `setTicker`. */
  setScript(script: CommentaryScript | null): void {
    if (script === null) {
      this.airing = null;
      this.guestSeat = null;
      return;
    }
    const guest = script.guest;
    this.guestSeat = guest
      ? { speakerId: guest.id, name: guest.name, x: GUEST_X, look: guestLook(guest), accent: guest.kit_primary, role: guest.role }
      : null;
    const pages = script.lines.map((line) => paginate(line.text, TEXT_W));
    const result = parseResult(script);
    this.airing = { script, pages, rows: pages.map((page) => Math.max(2, ...page.map((lines) => lines.length))), result };
    if (!this.tickerFixed) this.ticker = layoutTicker(tickerItems(script, result));
  }

  /** Headlines for the ticker, from the channel; they stay until replaced. */
  setTicker(items: string[]): void {
    this.tickerFixed = true;
    this.ticker = layoutTicker(items.length > 0 ? items : STAND_BY);
  }

  /** Everyone in a chair now: the hosts, and the guest if there is one. */
  private seated(): Seat[] {
    return this.guestSeat === null ? this.seats : [...this.seats, this.guestSeat];
  }

  /** Which seat a speaker sits in; speakers beyond the desk's seats share the last host's. */
  private seatOf(speakerId: string): number {
    const found = this.seated().findIndex((seat) => seat.speakerId === speakerId);
    return found >= 0 ? found : this.seats.length - 1;
  }

  /** The colour a speaker is shown in (their bubble arrow, lower third and tally light). */
  accentOf(speakerId: string): string {
    return this.seated()[this.seatOf(speakerId)]?.accent ?? "#f2c200";
  }

  draw(ctx: CanvasRenderingContext2D, t: number, options: FrameOptions = {}): void {
    ctx.imageSmoothingEnabled = false;
    const clock = options.clock ?? t;
    const airing = this.airing;
    const slides = airing?.script.slides ?? [];
    if (slides.length > 0) {
      drawSlides(ctx, slides, t, clock);
      drawBug(ctx, clock, options.replay);
      drawTicker(ctx, this.ticker, clock);
      return;
    }
    this.drawDesk(ctx, t, clock, options.notice ?? null, airing, options.replay ?? false);
  }

  private drawDesk(ctx: CanvasRenderingContext2D, t: number, clock: number, notice: Notice | null, airing: Airing | null, replay: boolean): void {
    const cue = airing === null || notice?.silent ? null : cueAt(airing.script, t);
    const seats = this.seated();
    const speakerSeat = cue === null ? -1 : this.seatOf(cue.line.speaker_id);
    const speaker = seats[speakerSeat];
    const typed = cue === null || airing === null ? null : typedAt(airing.pages[cue.index] ?? [], cue.elapsed, cue.duration);
    const speaking = typed?.speaking ?? false;
    ctx.drawImage(this.back, 0, 0);
    drawTopicScreen(ctx, notice ?? { label: airing === null ? "VPL News" : topicOf(airing.script, cue?.line ?? null) });
    drawRightScreen(ctx, airing?.script.screen ?? null, airing?.result ?? null);
    drawOnAir(ctx, clock);
    drawBug(ctx, clock, replay);
    if (speaker !== undefined) lightCone(ctx, speaker.x, 15, DESK_TOP, 16, 120, "#fff3c4", 0.05);
    seats.forEach((seat, index) => this.anchor(ctx, seats, seat, index, speakerSeat, speaking, clock));
    ctx.drawImage(this.front, 0, 0);
    if (this.guestSeat !== null) drawMic(ctx, this.guestSeat.x);
    seats.forEach((seat, index) => drawTally(ctx, seat.x, seat.accent, index === speakerSeat && speaking));
    if (airing !== null && cue !== null && typed !== null && speaker !== undefined) {
      drawBubble(ctx, { rows: airing.rows[cue.index] ?? 2, tailX: speaker.x, typed, t: clock });
      const alert = airing.script.alert;
      if (alert) drawBreakingBanner(ctx, alert, clock);
      else {
        const sameSpeaker = airing.script.lines[cue.index - 1]?.speaker_id === cue.line.speaker_id;
        const slide = sameSpeaker ? 1 : Math.min(1, cue.elapsed / SLIDE_SECONDS);
        drawLowerThird(ctx, cue.line.speaker_name, speaker.role ?? topicOf(airing.script, cue.line), speaker.accent, slide);
      }
    }
    drawTicker(ctx, this.ticker, clock);
  }

  private anchor(ctx: CanvasRenderingContext2D, seats: Seat[], seat: Seat, index: number, speakerSeat: number, speaking: boolean, clock: number): void {
    const talking = index === speakerSeat && speaking;
    const face: AnchorFace = {
      mouth: talking ? MOUTH_CYCLE[(Math.floor(clock * 9) + index * 5) % MOUTH_CYCLE.length]! : 0,
      blink: (clock + index * 1.7) % 4.1 < 0.13,
      gaze: speakerSeat < 0 || index === speakerSeat ? 0 : (Math.sign((seats[speakerSeat]?.x ?? seat.x) - seat.x) as -1 | 0 | 1),
      brow: talking && (Math.floor(clock * 2.2) + index) % 4 === 0 ? 1 : 0,
    };
    const breath = Math.sin(clock * 1.7 + index * 2.1) > 0.55 ? 1 : 0;
    const lift = talking && Math.sin(clock * 6.3 + index) > 0.8 ? 1 : 0;
    ctx.drawImage(anchorSprite(seat.look, face), seat.x - SPRITE_HALF, SPRITE_TOP + breath - lift);
  }
}
