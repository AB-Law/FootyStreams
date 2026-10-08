import type { Appearance, KitMeta, ReplayMeta } from "./meta.ts";

/** Skin tones 1 (lightest) to 8 (darkest). */
const SKIN_TONES = ["#ffdfc4", "#f0c8a0", "#e0ac80", "#c68642", "#a0692f", "#8d5524", "#6b4423", "#4a2c17"];
const DEFAULT_SKIN = "#c68642";

const HAIR_COLOURS: Record<string, string> = {
  black: "#1c1a1a",
  brown: "#5a3a22",
  blond: "#e6c35c",
  red: "#b5441f",
  grey: "#a8a8a8",
};
const DEFAULT_HAIR = "#3b2a1c";

/** Goalkeepers wear a plain colour that matches no kit in the default world. */
export const KEEPER_COLOURS = { home: "#f5a623", away: "#e84393" } as const;

/** Two kits closer than this (summed RGB difference) read as a clash on a small screen. */
const CLASH_DISTANCE = 120;

export interface Kit {
  pattern: KitMeta["pattern"];
  primary: string;
  secondary: string;
}

export function skinColour(appearance: Appearance): string {
  return SKIN_TONES[appearance.skin_tone - 1] ?? DEFAULT_SKIN;
}

export function hairColour(appearance: Appearance): string {
  return HAIR_COLOURS[appearance.hair_colour] ?? DEFAULT_HAIR;
}

function rgb(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

export function colourDistance(a: string, b: string): number {
  const [ar, ag, ab] = rgb(a);
  const [br, bg, bb] = rgb(b);
  return Math.abs(ar - br) + Math.abs(ag - bg) + Math.abs(ab - bb);
}

function toKit(meta: KitMeta): Kit {
  const [primary = "#ffffff", secondary = primary] = meta.colours;
  return { pattern: meta.pattern, primary, secondary };
}

/** The home side wears its home kit; the away side wears its home kit unless that clashes. */
export function pickKits(meta: ReplayMeta): { home: Kit; away: Kit } {
  const home = toKit(meta.home.kits.home);
  const away = toKit(meta.away.kits.home);
  const clash = colourDistance(home.primary, away.primary) < CLASH_DISTANCE;
  return { home, away: clash ? toKit(meta.away.kits.away) : away };
}

/** The shirt colour at column `column` and row `row` of the shirt (0-based, 5 wide, 3 tall). */
export function shirtColour(kit: Kit, column: number, row: number): string {
  const secondary =
    (kit.pattern === "stripes" && column % 2 === 1) ||
    (kit.pattern === "hoops" && row % 2 === 1) ||
    (kit.pattern === "halves" && column > 2) ||
    (kit.pattern === "sash" && column === row + 1);
  return secondary ? kit.secondary : kit.primary;
}
