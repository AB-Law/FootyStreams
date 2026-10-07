"""Matchday inputs built from a generated world: sides, tables, context and whole setups."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.match import MatchSetup
from footystreams.domain.mood import StateModifier
from footystreams.domain.world import World
from footystreams.league.setup import (
    MatchContext,
    SetupTables,
    TeamInputs,
    build_match_setup,
)
from tests.factories.league import make_fixture
from tests.factories.league_config import make_league_config, make_mood_config
from tests.factories.match import make_setup
from tests.factories.world import cached_static_tables, make_world


def make_setup_tables() -> SetupTables:
    """The committed roles, formations and league tables."""
    tables = cached_static_tables()
    return SetupTables(
        roles=tables.roles,
        formations=tables.formations,
        mood=make_mood_config(),
        recovery=make_league_config().recovery,
    )


def make_team_inputs(
    world: World,
    club_index: int = 0,
    modifiers: Mapping[str, Sequence[StateModifier]] | None = None,
) -> TeamInputs:
    """One club of ``world`` with its manager, staff and squad."""
    club = world.clubs[club_index]
    return TeamInputs(
        club=club,
        manager=next(m for m in world.managers if m.id == club.manager_id),
        staff=[s for s in world.staff if s.club_id == club.id],
        squad=[p for p in world.players if p.contract and p.contract.club_id == club.id],
        modifiers=modifiers or {},
    )


def make_match_context(world: World, home: int = 0, away: int = 1) -> MatchContext:
    """A fixture between two clubs of ``world`` with the factory weather and referee."""
    fixture = make_fixture(world, 1, home, away)
    reference = make_setup()
    return MatchContext(
        fixture=fixture,
        weather=reference.weather,
        referee_id=reference.referee_id,
        attendance=reference.attendance,
        today=fixture.date,
    )


def make_world_setup(seed: int = 1, home: int = 0, away: int = 1) -> MatchSetup:
    """A real setup between two clubs of the cached seed world."""
    world = make_world(seed)
    sides = (make_team_inputs(world, home), make_team_inputs(world, away))
    return build_match_setup(sides, make_match_context(world, home, away), make_setup_tables())
