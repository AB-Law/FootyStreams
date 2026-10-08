"""Wiring: load every static table the league layer reads (a composition-root helper)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from footystreams.league.climate import ClimateCatalog
from footystreams.league.config import LeagueConfig
from footystreams.league.development_config import DevelopmentConfig
from footystreams.league.matchday import MatchdayEngine
from footystreams.league.mood_config import MoodConfig
from footystreams.league.simulator import EventSimulator, MatchSimulator, ResultOnlySimulator
from footystreams.league.tables import LeagueTables
from footystreams.league.transfer_config import TransferConfig
from footystreams.persistence.ports import Repositories
from footystreams.seed.players.context import Geography
from footystreams.seed.prospects import SeedProspectFactory
from footystreams.seed.static.files import read_yaml
from footystreams.seed.static.tables import StaticTables, load_static_tables
from footystreams.sim import SimConfig, run_match
from footystreams.sim.tables import tables_from_catalog


def load_league_tables(
    directory: Path | None = None, static: StaticTables | None = None
) -> LeagueTables:
    """Roles, formations, injuries, climate, league and mood tables from ``data/static``."""
    tables = static or load_static_tables(directory)
    return LeagueTables(
        roles=tables.roles,
        formations=tables.formations,
        injuries=tables.injuries,
        climate=ClimateCatalog.model_validate(read_yaml("climate.yaml", directory)),
        config=LeagueConfig.model_validate(read_yaml("league.yaml", directory)),
        mood=MoodConfig.model_validate(read_yaml("mood.yaml", directory)),
        development=DevelopmentConfig.model_validate(read_yaml("development.yaml", directory)),
        transfer=TransferConfig.model_validate(read_yaml("transfer.yaml", directory)),
    )


class SimulatorKind(StrEnum):
    """Which match simulator plays the fixtures."""

    RESULT = "result"  # score only, fast: the default and the production fallback
    EVENT = "event"  # the real simulator with full event logs


def build_simulator(tables: LeagueTables, kind: SimulatorKind) -> MatchSimulator:
    """The simulator of ``kind``; the event simulator plays the formations the world defines."""
    if kind is SimulatorKind.RESULT:
        return ResultOnlySimulator(tables.roles, tables.config.result_only)
    config, sim_tables = SimConfig(), tables_from_catalog(tables.formations)
    return EventSimulator(lambda setup, seed: run_match(setup, seed, config, sim_tables))


def build_engine(
    tables: LeagueTables, world_seed: int, kind: SimulatorKind = SimulatorKind.RESULT
) -> MatchdayEngine:
    """The matchday engine over the chosen simulator."""
    return MatchdayEngine(
        tables=tables, simulator=build_simulator(tables, kind), world_seed=world_seed
    )


def build_prospects(repositories: Repositories, static: StaticTables) -> SeedProspectFactory:
    """The seed adapter that creates academy players, over the geography stored in the database."""
    nations = tuple(repositories.nations.all())
    cities = {
        nation.id: tuple(repositories.cities.find({"nation_id": nation.id})) for nation in nations
    }
    return SeedProspectFactory(static, Geography(nations, cities))
