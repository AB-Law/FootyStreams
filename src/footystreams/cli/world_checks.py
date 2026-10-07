"""Wiring: build the world-check inputs from the static tables (a composition-root helper)."""

from __future__ import annotations

from footystreams.seed.names.gates import normalise_list
from footystreams.seed.static.files import read_text_lines
from footystreams.seed.static.tables import StaticTables
from footystreams.verify import WorldChecks, WorldTargets


def build_world_checks(tables: StaticTables) -> WorldChecks:
    """Static tables and the denylist, as the world checks want them."""
    return WorldChecks(
        roles=tables.roles,
        formations=tables.formations,
        denylist=normalise_list(read_text_lines("denylist.txt")),
    )


def build_world_targets(tables: StaticTables) -> WorldTargets:
    """League-shape thresholds from ``club_archetypes.yaml`` (the single source)."""
    league = tables.clubs.league
    return WorldTargets(
        min_team_gap=league.min_gap,
        max_team_gap=league.max_gap,
        min_adjacent_gap=league.min_adjacent_gap,
    )
