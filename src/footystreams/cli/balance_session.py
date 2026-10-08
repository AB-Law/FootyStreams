"""What every ``balance`` command shares: the world, the tables, the config and the profile."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import yaml

from footystreams.balance import overrides
from footystreams.balance.runner import BalanceRunner
from footystreams.balance.scenarios import build_scenarios
from footystreams.balance.targets import Profile, load_profile
from footystreams.cli.league_wiring import load_league_tables
from footystreams.league.tables import LeagueTables
from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.world_store import save_world
from footystreams.seed.static.tables import load_static_tables
from footystreams.seed.world_io import read_world
from footystreams.sim import SimConfig
from footystreams.sim.tables import StaticTables, tables_from_catalog


def load_config(arguments: argparse.Namespace) -> SimConfig:
    """The defaults with ``--config`` and then every ``--set`` laid over them."""
    layers: list[dict[str, object]] = []
    if arguments.config is not None:
        loaded = yaml.safe_load(arguments.config.read_text(encoding="utf-8")) or {}
        layers.append(loaded)
    layers += [overrides.parse_pair(pair) for pair in arguments.pairs]
    return overrides.apply(SimConfig(), overrides.combine(layers))


@dataclass(frozen=True, slots=True)
class Session:
    """The loaded world and settings of one invocation."""

    arguments: argparse.Namespace
    config: SimConfig
    profile: Profile
    league_tables: LeagueTables
    sim_tables: StaticTables
    database: InMemoryDatabase

    def runner(self, matches: int | None = None, seed: int | None = None) -> BalanceRunner:
        """A runner over ``matches`` scenarios from ``seed`` (command-line values by default)."""
        arguments = self.arguments
        with InMemoryUnitOfWork(self.database) as uow:
            scenarios = build_scenarios(
                uow,
                self.league_tables,
                arguments.matches if matches is None else matches,
                arguments.seed if seed is None else seed,
            )
        return BalanceRunner(scenarios, self.sim_tables, arguments.workers)


def open_session(arguments: argparse.Namespace) -> Session:
    """Load the profile, config and world named on the command line."""
    league_tables = load_league_tables(static=load_static_tables())
    database = InMemoryDatabase()
    save_world(read_world(arguments.world), InMemoryUnitOfWork(database))
    return Session(
        arguments=arguments,
        config=load_config(arguments),
        profile=load_profile(arguments.profile),
        league_tables=league_tables,
        sim_tables=tables_from_catalog(league_tables.formations),
        database=database,
    )
