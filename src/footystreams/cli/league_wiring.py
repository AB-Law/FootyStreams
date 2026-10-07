"""Wiring: load every static table the league layer reads (a composition-root helper)."""

from __future__ import annotations

from pathlib import Path

from footystreams.league.climate import ClimateCatalog
from footystreams.league.config import LeagueConfig
from footystreams.league.development_config import DevelopmentConfig
from footystreams.league.matchday import MatchdayEngine
from footystreams.league.mood_config import MoodConfig
from footystreams.league.simulator import ResultOnlySimulator
from footystreams.league.tables import LeagueTables
from footystreams.seed.static.files import read_yaml
from footystreams.seed.static.tables import StaticTables, load_static_tables


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
    )


def build_engine(tables: LeagueTables, world_seed: int) -> MatchdayEngine:
    """The matchday engine with the result-only simulator (the event simulator plugs in here)."""
    simulator = ResultOnlySimulator(tables.roles, tables.config.result_only)
    return MatchdayEngine(tables=tables, simulator=simulator, world_seed=world_seed)
