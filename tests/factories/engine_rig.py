"""A small league and an engine over it, for the runtime tests (virtual clock, file SQLite)."""

from __future__ import annotations

import asyncio
import datetime as dt
import shutil
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from footystreams.league.daily import DayReport
from footystreams.league.matchday import MatchdayEngine
from footystreams.league.season import SeasonRunner
from footystreams.league.simulator import EventSimulator
from footystreams.persistence.ports import UnitOfWorkFactory
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.migrate import upgrade
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import save_world
from footystreams.runtime.clock import VirtualClock
from footystreams.runtime.config import EngineConfig, parse_pace
from footystreams.runtime.sinks import InMemorySink
from footystreams.runtime.world import WorldStepper
from footystreams.sim import SimConfig, run_match
from footystreams.sim.tables import tables_from_catalog
from tests.factories.league_inputs import make_league_tables
from tests.factories.league_run import make_engine, make_prospects
from tests.factories.world import make_world

if TYPE_CHECKING:
    from footystreams.runtime.bus import EventSink
    from footystreams.runtime.engine import Engine

SEED, CLUBS = 2, 4


async def no_pause(_: float) -> None:
    """A sleep that does not wait (retry backoff and restart pauses in tests)."""
    await asyncio.sleep(0)


def real_engine() -> MatchdayEngine:
    """The matchday engine over the real event simulator, as in production.

    The result-only simulator writes thin logs that ``verify_match`` rightly rejects (its score and
    clock do not follow from its events), so the engine tests play real matches.
    """
    tables = make_league_tables()
    sim_tables, config = tables_from_catalog(tables.formations), SimConfig()
    simulator = EventSimulator(lambda setup, seed: run_match(setup, seed, config, sim_tables))
    return MatchdayEngine(tables=tables, simulator=simulator, world_seed=SEED)


@cache
def _template_database() -> Path:
    """The seeded database, built once per process and copied for every test."""
    path = Path(tempfile.mkdtemp(prefix="footy-engine-rig-")) / "template.sqlite"
    engine = create_sqlite_engine(path)
    upgrade(engine)
    save_world(make_world(SEED, CLUBS), SqlUnitOfWork(engine))
    engine.dispose()  # closes the last connection, which folds the WAL into the file
    return path


def file_factory(path: Path) -> UnitOfWorkFactory:
    """A SQLite file holding the seed world (safe to use from several threads)."""
    shutil.copyfile(_template_database(), path)
    engine = create_sqlite_engine(path)

    def factory() -> SqlUnitOfWork:
        return SqlUnitOfWork(engine)

    return factory


class Rig:
    """One league database, its world stepper and an in-memory archive sink."""

    def __init__(self, directory: Path, *, rollover: bool = False, thin: bool = False) -> None:
        """Build the database under ``directory``.

        ``rollover`` lets it play several seasons; ``thin`` plays with the result-only simulator
        (about 11 events a match) for tests of the engine's own logic, where real 1,400-event
        matches would only make saving the cursor on every event slow. Thin logs fail
        ``verify_match``, so those tests switch verification off or replace it.
        """
        directory.mkdir(parents=True, exist_ok=True)
        self.db_path = directory / "league.sqlite"
        self.factory = file_factory(self.db_path)
        prospects = make_prospects(SEED, CLUBS) if rollover else None
        self.runner = SeasonRunner(
            self.factory, make_engine(SEED) if thin else real_engine(), prospects
        )
        self.stepper = WorldStepper(self.runner, self.factory)
        self.sink = InMemorySink(critical=True)
        self.clock = VirtualClock()

    def matchday_dates(self) -> list[dt.date]:
        """The date of every matchday of the first season."""
        with self.factory() as uow:
            season = uow.seasons.all()[0]
        self.runner.prepare(season)
        with self.factory() as uow:
            return sorted({fixture.date for fixture in uow.fixtures.all()})

    def config(self, **changes: object) -> EngineConfig:
        """An instant-pace configuration; override any setting by name."""
        settings: dict[str, object] = {
            "db_path": self.db_path,
            "pace": parse_pace("instant"),
            "sinks": ("memory",),
            "starve_grace_s": 2.0,
            "cursor_every": 25,
        }
        return EngineConfig(**{**settings, **changes})  # type: ignore[arg-type]

    def engine(
        self,
        config: EngineConfig,
        *,
        step: Callable[[], DayReport] | None = None,
        extra_sinks: tuple[EventSink, ...] = (),
    ) -> Engine:
        """An engine over this rig; its archive sink is ``self.sink``."""
        from footystreams.runtime.engine import (  # noqa: PLC0415 - lazy: the buffer tests need no engine
            Engine,
            EngineParts,
        )

        parts = EngineParts(
            factory=self.factory,
            step=step or self.stepper,
            sinks=[self.sink, *extra_sinks],
            clock=self.clock,
            sleep=no_pause,
        )
        return Engine(config, parts)
