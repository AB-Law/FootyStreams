"""A seeded world loaded into an in-memory database, as the league layer sees it."""

from __future__ import annotations

from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.ports import UnitOfWorkFactory
from footystreams.persistence.world_store import save_world
from tests.factories.world import make_world


def make_league_db(seed: int = 1, clubs: int = 8) -> UnitOfWorkFactory:
    """Units of work over a fresh in-memory database holding ``make_world(seed, clubs)``."""
    database = InMemoryDatabase()
    save_world(make_world(seed, clubs), InMemoryUnitOfWork(database))
    return lambda: InMemoryUnitOfWork(database)
