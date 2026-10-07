"""Run a seed world through the league: engine, runner and a played season."""

from __future__ import annotations

import hashlib
from functools import cache

from footystreams.domain.canonical import canonical_json
from footystreams.domain.world import World
from footystreams.league.matchday import MatchdayEngine
from footystreams.league.season import SeasonResult, SeasonRunner
from footystreams.league.simulator import ResultOnlySimulator
from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.ports import UnitOfWork, UnitOfWorkFactory
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.migrate import upgrade
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import save_world
from footystreams.seed.prospects import SeedProspectFactory
from tests.factories.league_inputs import make_league_tables
from tests.factories.world import make_generation_context, make_world


def make_engine(world_seed: int) -> MatchdayEngine:
    """The matchday engine over the committed tables and the result-only simulator."""
    tables = make_league_tables()
    simulator = ResultOnlySimulator(tables.roles, tables.config.result_only)
    return MatchdayEngine(tables=tables, simulator=simulator, world_seed=world_seed)


def make_factory(world: World, backend: str = "memory") -> UnitOfWorkFactory:
    """A fresh empty database of the named backend (memory or sql) holding ``world``."""
    if backend == "sql":
        engine = create_sqlite_engine()
        upgrade(engine)

        def sql_factory() -> UnitOfWork:
            return SqlUnitOfWork(engine)

        save_world(world, sql_factory())
        return sql_factory
    database = InMemoryDatabase()
    save_world(world, InMemoryUnitOfWork(database))

    def memory_factory() -> UnitOfWork:
        return InMemoryUnitOfWork(database)

    return memory_factory


def make_runner(
    seed: int = 1, clubs: int = 8, backend: str = "memory"
) -> tuple[SeasonRunner, UnitOfWorkFactory]:
    """A fresh database with the seed world, and a runner over it."""
    factory = make_factory(make_world(seed, clubs), backend)
    return SeasonRunner(factory, make_engine(seed)), factory


def play_season(
    seed: int = 1, clubs: int = 8, backend: str = "memory"
) -> tuple[SeasonResult, UnitOfWorkFactory]:
    """Run the first season of the seed world to its end."""
    runner, factory = make_runner(seed, clubs, backend)
    with factory() as uow:
        season = uow.seasons.all()[0]
    return runner.run_season(season), factory


@cache
def cached_season(seed: int = 1) -> tuple[SeasonResult, UnitOfWorkFactory]:
    """A played season shared by read-only tests (do not write to its database)."""
    return play_season(seed)


@cache
def cached_small_season() -> tuple[SeasonResult, UnitOfWorkFactory]:
    """A played four-club season (fast enough for the T0 tier); do not write to its database."""
    return play_season(2, 4)


def season_fingerprint(factory: UnitOfWorkFactory) -> str:
    """SHA-256 over the standings snapshots, the ledger and the match digests, in key order."""
    with factory() as uow:
        document = {
            "standings": [s.model_dump(mode="json") for s in uow.standings.all()],
            "ledger": [e.model_dump(mode="json") for e in uow.ledger.all()],
            "matches": [[m.id, m.log_digest] for m in uow.matches.all()],
            "players": [p.model_dump(mode="json") for p in uow.players.all()],
        }
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()


def make_prospects(seed: int = 1, clubs: int = 8) -> SeedProspectFactory:
    """The seed adapter that creates academy players and journeymen for the rollover."""
    context = make_generation_context(seed)
    return SeedProspectFactory(context.tables, context.geography)


def make_multi_runner(
    seed: int = 1, clubs: int = 8, backend: str = "memory"
) -> tuple[SeasonRunner, UnitOfWorkFactory]:
    """Like ``make_runner`` but with the rollover enabled."""
    factory = make_factory(make_world(seed, clubs), backend)
    return SeasonRunner(factory, make_engine(seed), make_prospects(seed, clubs)), factory


def play_seasons(
    count: int, seed: int = 2, clubs: int = 4, backend: str = "memory"
) -> tuple[list[SeasonResult], UnitOfWorkFactory]:
    """Run ``count`` seasons with the off-season rollover after each."""
    runner, factory = make_multi_runner(seed, clubs, backend)
    return runner.run_seasons(count), factory


@cache
def cached_rolled_over() -> tuple[list[SeasonResult], UnitOfWorkFactory]:
    """One four-club season plus its rollover; do not write to its database."""
    return play_seasons(1)
