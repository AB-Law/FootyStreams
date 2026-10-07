"""Matchday inputs built from a generated world: sides, tables, context and whole setups."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.match import MatchSetup
from footystreams.domain.mood import StateModifier
from footystreams.domain.world import World
from footystreams.league.climate import ClimateCatalog
from footystreams.league.post_match import PlayedFixture, PostMatchTables
from footystreams.league.setup import (
    MatchContext,
    SetupTables,
    TeamInputs,
    build_match_setup,
)
from footystreams.league.simulator import ResultOnlySimulator
from footystreams.league.tables import LeagueTables
from footystreams.seed.static.files import read_yaml
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


def make_post_match_tables() -> PostMatchTables:
    """The committed injury, recovery, finance and mood tables."""
    config = make_league_config()
    return PostMatchTables(
        injuries=cached_static_tables().injuries,
        recovery=config.recovery,
        finance=config.finance,
        mood=make_mood_config(),
    )


def make_played_fixture(sim_seed: int = 5, world_seed: int = 1) -> PlayedFixture:
    """Clubs 0 and 1 of the seed world playing matchday 1 with the result-only simulator."""
    world = make_world(world_seed)
    teams = (make_team_inputs(world, 0), make_team_inputs(world, 1))
    context = make_match_context(world, 0, 1)
    setup = build_match_setup(teams, context, make_setup_tables())
    simulator = ResultOnlySimulator(cached_static_tables().roles, make_league_config().result_only)
    return PlayedFixture(
        fixture=context.fixture,
        setup=setup,
        result=simulator.simulate(setup, sim_seed),
        teams=teams,
        today=context.today,
    )


def make_league_tables() -> LeagueTables:
    """Every committed static table the league layer reads."""
    static = cached_static_tables()
    return LeagueTables(
        roles=static.roles,
        formations=static.formations,
        injuries=static.injuries,
        climate=ClimateCatalog.model_validate(read_yaml("climate.yaml")),
        config=make_league_config(),
        mood=make_mood_config(),
    )
