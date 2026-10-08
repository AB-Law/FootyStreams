"""Resolve ``sim --home A --away B`` from a world: a friendly between two of its clubs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from footystreams.cli.league_wiring import build_engine, load_league_tables
from footystreams.domain.match import MatchSetup
from footystreams.domain.referee import Referee
from footystreams.league.clock import read_date
from footystreams.league.friendly import build_friendly_setup, find_club
from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.ports import UnitOfWork, UnitOfWorkFactory
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import KEY_WORLD_SEED, read_meta, save_world
from footystreams.seed.static.tables import StaticTables as SeedTables
from footystreams.seed.static.tables import load_static_tables
from footystreams.seed.world_io import read_world
from footystreams.sim.tables import StaticTables, tables_from_catalog


@dataclass(frozen=True, slots=True)
class WorldMatch:
    """What the simulator needs to play a friendly drawn from a world."""

    setup: MatchSetup
    tables: StaticTables
    referee: Referee


def _factory(world: Path | None, database: Path | None) -> UnitOfWorkFactory:
    if database is not None:
        engine = create_sqlite_engine(database)
        return lambda: SqlUnitOfWork(engine)
    if world is None:
        msg = "pass --demo, or both --home and --away with --world DIR or --db FILE"
        raise ValueError(msg)
    memory = InMemoryDatabase()
    save_world(read_world(world), InMemoryUnitOfWork(memory))
    return lambda: InMemoryUnitOfWork(memory)


def resolve_world_match(arguments: argparse.Namespace) -> WorldMatch:
    """Look up both clubs and build their friendly as of the world's current date."""
    if arguments.home is None or arguments.away is None:
        msg = "pass --demo, or both --home and --away with --world DIR or --db FILE"
        raise ValueError(msg)
    static = load_static_tables()
    with _factory(arguments.world, arguments.db)() as uow:
        return _friendly(uow, arguments, static)


def _friendly(uow: UnitOfWork, arguments: argparse.Namespace, static: SeedTables) -> WorldMatch:
    tables = load_league_tables(static=static)
    engine = build_engine(tables, int(read_meta(uow, KEY_WORLD_SEED)))
    home, away = find_club(uow, arguments.home), find_club(uow, arguments.away)
    setup = build_friendly_setup(uow, home.id, away.id, engine, read_date(uow))
    return WorldMatch(
        setup=setup,
        tables=tables_from_catalog(tables.formations),
        referee=uow.referees.require(setup.referee_id),
    )
