"""Wiring for ``uv run engine``: the database, the world step in a worker process, the engine.

The world step (the league's daily tick and the simulator) is CPU-bound pure Python, so it runs
in its own process: the engine's event loop and the paced playback never wait on the interpreter
lock behind a match being simulated. The worker builds its own database connection and league
objects from plain arguments (they are not picklable), keeps them for its lifetime and answers one
call per in-world day.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from footystreams.cli.league_wiring import (
    SimulatorKind,
    build_engine,
    build_prospects,
    load_league_tables,
)
from footystreams.league.daily import DayReport
from footystreams.league.season import SeasonRunner
from footystreams.persistence.ports import NotFoundError, UnitOfWorkFactory
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.migrate import upgrade
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import KEY_WORLD_SEED, read_meta, save_world
from footystreams.runtime.bus import EventSink
from footystreams.runtime.config import EngineConfig
from footystreams.runtime.engine import Engine, EngineParts
from footystreams.runtime.world import WorldStepper
from footystreams.seed.static.tables import load_static_tables
from footystreams.seed.world_io import read_world

_STEPPER: WorldStepper | None = None


def sql_factory(db_path: Path) -> UnitOfWorkFactory:
    """Units of work over the SQLite file (WAL, safe to share between threads)."""
    engine = create_sqlite_engine(db_path)

    def factory() -> SqlUnitOfWork:
        return SqlUnitOfWork(engine)

    return factory


def prepare_database(db_path: Path, world_dir: Path | None) -> None:
    """Create and fill the database from ``world_dir`` if it has no world yet; else leave it be."""
    engine = create_sqlite_engine(db_path)
    upgrade(engine)
    factory = sql_factory(db_path)
    with factory() as uow:
        try:
            read_meta(uow, KEY_WORLD_SEED)
        except NotFoundError:
            if world_dir is None:
                msg = f"{db_path} holds no world; pass --world DIR to create one"
                raise ValueError(msg) from None
            save_world(read_world(world_dir), factory())
    engine.dispose()


def _start_worker(db_path: str, simulator: str) -> None:
    """Build the league objects inside the worker process (runs once, in the initializer)."""
    global _STEPPER  # noqa: PLW0603 - per-process state, set once by the pool initializer
    factory = sql_factory(Path(db_path))
    static = load_static_tables()
    tables = load_league_tables(static=static)
    with factory() as uow:
        world_seed = int(read_meta(uow, KEY_WORLD_SEED))
        prospects = build_prospects(uow, static)
    runner = SeasonRunner(
        factory, build_engine(tables, world_seed, SimulatorKind(simulator)), prospects
    )
    _STEPPER = WorldStepper(runner, factory)


def world_step() -> DayReport:
    """Play one in-world day (the function the pool runs in the worker process)."""
    if _STEPPER is None:
        msg = "the world worker was not initialised"
        raise RuntimeError(msg)
    return _STEPPER()


def make_pool(db_path: Path, simulator: SimulatorKind) -> ProcessPoolExecutor:
    """One worker process that owns the league objects and plays the days, one at a time."""
    return ProcessPoolExecutor(
        max_workers=1, initializer=_start_worker, initargs=(str(db_path), simulator.value)
    )


def make_engine(config: EngineConfig, sinks: list[EventSink], pool: ProcessPoolExecutor) -> Engine:
    """The engine over the database named in ``config``, stepping the world in ``pool``."""
    return Engine(
        config,
        EngineParts(
            factory=sql_factory(config.db_path),
            step=world_step,
            sinks=sinks,
            clock=config.pace.clock(),
            executor=pool,
        ),
    )
