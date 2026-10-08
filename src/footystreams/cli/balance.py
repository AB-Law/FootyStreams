"""``uv run balance``: play many matches over a world and compare them with a balance profile.

A thin wrapper over the ``balance`` library. The world is loaded once, every ordered pairing of its
clubs is played in turn, and the result is printed as a table of value, interval, band and verdict.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import ValidationError

from footystreams.balance import overrides
from footystreams.balance.evaluate import MetricResult, evaluate, failures
from footystreams.balance.report import format_failures, format_report
from footystreams.balance.runner import BalanceRunner, default_workers
from footystreams.balance.scenarios import Scenario, build_scenarios
from footystreams.balance.targets import DEFAULT_PROFILE, Profile, load_profile
from footystreams.cli.league_wiring import load_league_tables
from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.world_store import save_world
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.static.tables import load_static_tables
from footystreams.seed.world_io import WorldFileError, read_world
from footystreams.sim import SimConfig
from footystreams.sim.tables import StaticTables, tables_from_catalog
from footystreams.tools.paths import PROJECT_ROOT

DEFAULT_WORLD = PROJECT_ROOT / "data" / "worlds" / "default"
DEFAULT_MATCHES = 1200
DEFAULT_SEED = 1
EXIT_OK, EXIT_OFF_TARGET, EXIT_USAGE = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(prog="balance", description=__doc__)
    parser.add_argument(
        "--profile", default=DEFAULT_PROFILE, help="balance profile (default realistic)"
    )
    parser.add_argument("--matches", type=int, default=DEFAULT_MATCHES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="base seed of the run")
    parser.add_argument(
        "--world", type=Path, default=DEFAULT_WORLD, help="world to play (a directory)"
    )
    parser.add_argument("--config", type=Path, help="partial SimConfig YAML laid over the defaults")
    parser.add_argument(
        "--set", action="append", default=[], dest="pairs", metavar="GROUP.KNOB=VALUE",
        help="override one knob (repeatable)",
    )  # fmt: skip
    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--failures", action="store_true", help="print only the metrics that miss")
    return parser


def load_config(arguments: argparse.Namespace) -> SimConfig:
    """The defaults with ``--config`` and then every ``--set`` laid over them."""
    layers: list[dict[str, object]] = []
    if arguments.config is not None:
        loaded = yaml.safe_load(arguments.config.read_text(encoding="utf-8")) or {}
        layers.append(loaded)
    layers += [overrides.parse_pair(pair) for pair in arguments.pairs]
    return overrides.apply(SimConfig(), overrides.combine(layers))


def open_scenarios(arguments: argparse.Namespace) -> tuple[list[Scenario], StaticTables]:
    """Load the world and build the matches to play, with the sim tables for its formations."""
    tables = load_league_tables(static=load_static_tables())
    database = InMemoryDatabase()
    save_world(read_world(arguments.world), InMemoryUnitOfWork(database))
    with InMemoryUnitOfWork(database) as uow:
        scenarios = build_scenarios(uow, tables, arguments.matches, arguments.seed)
    return scenarios, tables_from_catalog(tables.formations)


def _print_report(results: Sequence[MetricResult], arguments: argparse.Namespace) -> None:
    print(format_report(results, arguments.matches, arguments.profile))
    if arguments.failures and failures(results):
        print()
        print(format_failures(results))


def _measure(arguments: argparse.Namespace, profile: Profile) -> list[MetricResult]:
    config = load_config(arguments)
    scenarios, sim_tables = open_scenarios(arguments)
    with BalanceRunner(scenarios, sim_tables, arguments.workers) as runner:
        return evaluate(runner.run(config), profile.metrics)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the exit code (0 all PASS, 1 some metric misses, 2 usage)."""
    arguments = build_parser().parse_args(argv)
    try:
        results = _measure(arguments, load_profile(arguments.profile))
    except (ValueError, ValidationError, StaticDataError, WorldFileError, OSError) as error:
        print(f"balance: error: {error}", file=sys.stderr)
        return EXIT_USAGE
    _print_report(results, arguments)
    return EXIT_OFF_TARGET if failures(results) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
