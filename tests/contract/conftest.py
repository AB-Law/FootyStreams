"""Backends under contract: every repository test runs against both implementations."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import Engine

from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.ports import UnitOfWork
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.migrate import upgrade
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import save_world
from tests.factories.world import make_world

UowFactory = Callable[[], UnitOfWork]
BACKENDS = ("memory", "sql")


def build_backend(name: str) -> tuple[UowFactory, Engine | None]:
    """A fresh empty database of the named backend and a factory for units of work on it."""
    if name == "memory":
        database = InMemoryDatabase()
        return (lambda: InMemoryUnitOfWork(database)), None
    engine = create_sqlite_engine()
    upgrade(engine)
    return (lambda: SqlUnitOfWork(engine)), engine


@pytest.fixture(params=BACKENDS)
def empty_backend(request: pytest.FixtureRequest) -> tuple[UowFactory, Engine | None]:
    """An empty database per test."""
    return build_backend(request.param)


@pytest.fixture(params=BACKENDS, scope="module")
def loaded(request: pytest.FixtureRequest) -> UowFactory:
    """A database holding the seed-1 world, shared by read-only and roll-back-only tests."""
    factory, _ = build_backend(request.param)
    save_world(make_world(1), factory())
    return factory
