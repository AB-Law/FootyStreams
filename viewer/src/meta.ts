// The replay's lookup tables, written by scripts/record_match.py (frames only carry player ids).

export interface Appearance {
  skin_tone: number;
  hair_style: string;
  hair_colour: string;
  facial_hair: string;
  build: string;
}

export interface PlayerMeta {
  name: string;
  number: number | null;
  appearance: Appearance;
}

export interface KitMeta {
  pattern: "solid" | "stripes" | "hoops" | "halves" | "sash";
  colours: string[];
}

export interface TeamMeta {
  name: string;
  short_code: string;
  kits: { home: KitMeta; away: KitMeta };
  players: Record<string, PlayerMeta>;
}

export interface ReplayMeta {
  match_id: string;
  home: TeamMeta;
  away: TeamMeta;
}

export type TeamSide = "home" | "away";

export function teamOf(meta: ReplayMeta, playerId: string): TeamSide | null {
  if (playerId in meta.home.players) return "home";
  if (playerId in meta.away.players) return "away";
  return null;
}

export function playerName(meta: ReplayMeta, playerId: string): string {
  const side = teamOf(meta, playerId);
  return side === null ? playerId : (meta[side].players[playerId]?.name ?? playerId);
}
