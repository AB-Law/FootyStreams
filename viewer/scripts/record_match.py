"""Record a friendly as a replay for the pixel viewer: `<out>.ndjson` plus `<out>.meta.json`.

The NDJSON is the sim's own event log with one tracking frame per second. Frames only carry player
ids, so the meta file adds what the viewer needs to dress them: club names, kits and, per player,
name, shirt number, team and appearance. Run it from the repository root:

    uv run python viewer/scripts/record_match.py --home SEI --away BUK --out viewer/public/replay
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from footystreams.cli.sim_world import WorldMatch, resolve_world_match
from footystreams.domain.match import TeamSheet
from footystreams.domain.player import Player
from footystreams.seed.world_io import read_world
from footystreams.sim import SimConfig, run_match

DEFAULT_WORLD = Path("data/worlds/default")


def _team_meta(
    sheet: TeamSheet, kit_name: str, appearances: dict[str, Player]
) -> dict[str, object]:
    """Club identity, kit and every squad player of one side."""
    colours = sheet.club.colours
    kit = colours.home_kit if kit_name == "home" else colours.away_kit
    players = {}
    for player_id, snapshot in sheet.squad.items():
        look = appearances[player_id].appearance
        players[player_id] = {
            "name": snapshot.known_as,
            "number": snapshot.squad_number,
            "appearance": look.model_dump(mode="json"),
        }
    return {
        "name": sheet.club.name,
        "short_code": sheet.club.short_code,
        "kit": {"pattern": kit.pattern.value, "colours": list(kit.colours)},
        "players": players,
    }


def build_meta(found: WorldMatch, world_dir: Path) -> dict[str, object]:
    """The viewer's lookup tables for the two sides of a recorded match."""
    people = {player.id: player for player in read_world(world_dir).players}
    return {
        "match_id": found.setup.match_id,
        "home": _team_meta(found.setup.home, "home", people),
        "away": _team_meta(found.setup.away, "away", people),
    }


def main() -> None:
    """Play the friendly and write the replay files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, help="club id, short code or name")
    parser.add_argument("--away", required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    parser.add_argument("--out", type=Path, required=True, help="path without extension")
    arguments = parser.parse_args()
    arguments.db = None  # resolve_world_match also accepts a SQLite file; the viewer uses a world
    found = resolve_world_match(arguments)
    config = SimConfig(emit_frames=True, frame_interval_s=1)
    result = run_match(found.setup, arguments.seed, config, found.tables, found.referee)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    lines = (event.model_dump_json() for event in result.events)
    arguments.out.with_suffix(".ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = build_meta(found, arguments.world)
    arguments.out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
