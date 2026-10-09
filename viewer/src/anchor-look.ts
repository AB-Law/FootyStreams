import type { Guest } from "./commentary.ts";
import type { Appearance } from "./meta.ts";

// Who an anchor is and what their face is doing. A look is worked out from the speaker's id, so the
// same person is dressed the same way every time the desk is shown.

export interface AnchorLook {
  appearance: Appearance;
  jacket: string;
  accent: string;
  tie: boolean;
  glasses: boolean;
}

export interface AnchorFace {
  /** 0 closed, then 1 to 3 opening wider. */
  mouth: 0 | 1 | 2 | 3;
  blink: boolean;
  /** Which way the eyes look: -1 left of the screen, 1 right. */
  gaze: -1 | 0 | 1;
  brow: 0 | 1;
}

export const JACKETS = ["#1d3557", "#2b2f3a", "#4a2a5a", "#1f4d45", "#5a2a2e"] as const;
export const ACCENTS = ["#c8102e", "#f2c200", "#e8e8ee", "#e07a1f", "#3aa6c9"] as const;

const HAIR_STYLES = ["short", "short", "buzz", "fade", "curly", "long", "braids", "bald"] as const;
const HAIR_COLOURS = ["black", "brown", "brown", "blond", "red", "grey"] as const;
const FACIAL_HAIR = ["none", "none", "none", "stubble", "beard", "goatee"] as const;
const BUILDS = ["lean", "average", "average", "stocky"] as const;

function hashOf(text: string): number {
  let hash = 2166136261;
  for (const char of text) hash = Math.imul(hash ^ (char.codePointAt(0) ?? 0), 16777619) >>> 0;
  return hash;
}

/** A small seeded generator (mulberry32): the same seed always gives the same run of numbers. */
function randomFrom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = Math.imul(state ^ (state >>> 15), state | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

/** The look for a speaker. `seat` picks the jacket, so neighbours at the desk never match. */
export function lookFor(speakerId: string, seat: number): AnchorLook {
  const next = randomFrom(hashOf(speakerId));
  const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
  const hairStyle = pick(HAIR_STYLES);
  const longHair = hairStyle === "long" || hairStyle === "braids";
  return {
    appearance: {
      skin_tone: 1 + Math.floor(next() * 8),
      hair_style: hairStyle,
      hair_colour: pick(HAIR_COLOURS),
      facial_hair: longHair ? "none" : pick(FACIAL_HAIR),
      build: pick(BUILDS),
    },
    jacket: JACKETS[seat % JACKETS.length] as string,
    accent: ACCENTS[(seat * 2 + 1) % ACCENTS.length] as string,
    tie: next() < 0.6,
    glasses: next() < 0.3,
  };
}

/**
 * The looks for everyone at the desk, in seat order. Two people never share a hairstyle: a repeat is
 * swapped for the first style not yet taken, so a full desk is easy to tell apart at a glance.
 */
export function castLooks(speakerIds: string[]): AnchorLook[] {
  const taken = new Set<string>();
  return speakerIds.map((id, seat) => {
    const look = lookFor(id, seat);
    const style = look.appearance.hair_style;
    const free = taken.has(style) ? ([...new Set(HAIR_STYLES)].find((candidate) => !taken.has(candidate)) ?? style) : style;
    taken.add(free);
    if (free === style) return look;
    const longHair = free === "long" || free === "braids";
    return { ...look, appearance: { ...look.appearance, hair_style: free, facial_hair: longHair ? "none" : look.appearance.facial_hair } };
  });
}

/** A guest looks like themselves: their own face and hair, in the colours of their club. */
export function guestLook(guest: Guest): AnchorLook {
  const find = (key: string, fallback: string): string => String(guest.appearance[key] ?? fallback);
  return {
    appearance: {
      skin_tone: Number(guest.appearance.skin_tone ?? 3),
      hair_style: find("hair_style", "short"),
      hair_colour: find("hair_colour", "brown"),
      facial_hair: find("facial_hair", "none"),
      build: find("build", "average"),
    },
    jacket: guest.kit_primary,
    accent: guest.kit_secondary,
    tie: false,
    glasses: false,
  };
}
