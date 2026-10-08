"""Scenarios for the balance harness tests: a generated 4-club world and its sim tables."""

from __future__ import annotations

from functools import cache

from footystreams.balance.scenarios import Scenario, build_scenarios
from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.world_store import save_world
from footystreams.sim.tables import StaticTables, tables_from_catalog
from tests.factories.league_inputs import make_league_tables
from tests.factories.world import make_world


@cache
def make_balance_scenarios(
    matches: int = 12, seed: int = 1, min_gap: float = 0.0
) -> tuple[Scenario, ...]:
    """Scenarios over a generated 4-club world (12 ordered pairings)."""
    database = InMemoryDatabase()
    save_world(make_world(2, 4), InMemoryUnitOfWork(database))
    with InMemoryUnitOfWork(database) as uow:
        return tuple(build_scenarios(uow, make_league_tables(), matches, seed, min_gap))


def make_balance_tables() -> StaticTables:
    """The sim tables for the generated world's formations."""
    return tables_from_catalog(make_league_tables().formations)
