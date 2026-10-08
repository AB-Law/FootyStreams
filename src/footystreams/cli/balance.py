"""``uv run balance``: play many matches over a world and compare them with a balance profile.

A thin wrapper over the ``balance`` library. The world is loaded once and every ordered pairing of
its clubs is played in turn. Commands: ``run`` (the default) prints the targets table;
``sensitivity`` nudges knobs and prints which knob moves which metric.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import yaml
from pydantic import ValidationError

from footystreams.balance import knobs, overrides
from footystreams.balance.evaluate import evaluate, failures
from footystreams.balance.report import format_failures, format_report
from footystreams.balance.runner import BalanceRunner, default_workers
from footystreams.balance.scenarios import Scenario, build_scenarios
from footystreams.balance.sensitivity import (
    DEFAULT_RELATIVE_STEP,
    format_matrix,
    noise_floor,
    strongest,
    sweep,
)
from footystreams.balance.targets import DEFAULT_PROFILE, Profile, Target, load_profile
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
COMMANDS = ("run", "sensitivity")
# The columns of the sensitivity matrix unless --metrics says otherwise: the headline numbers.
MATRIX_METRICS = (
    "goals_per_match",
    "shots_per_team",
    "on_target_per_shot",
    "goals_per_shot_pct",
    "pass_completion_pct",
    "draw_pct",
    "fouls_per_match",
    "yellows_per_match",
    "reds_per_match",
    "corners_per_match",
    "offsides_per_match",
)
STRONGEST_PER_METRIC = 3


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(prog="balance", description=__doc__)
    parser.add_argument("command", nargs="?", choices=COMMANDS, default="run")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="balance profile (realistic)")
    parser.add_argument("--matches", type=int, default=DEFAULT_MATCHES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="base seed of the run")
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD, help="world directory to play")
    parser.add_argument("--config", type=Path, help="partial SimConfig YAML laid over the defaults")
    parser.add_argument(
        "--set", action="append", default=[], dest="pairs", metavar="GROUP.KNOB=VALUE",
        help="override one knob (repeatable)",
    )  # fmt: skip
    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--failures", action="store_true", help="run: only the metrics that miss")
    parser.add_argument("--knobs", help="sensitivity: comma-separated knob paths to nudge")
    parser.add_argument("--group", help="sensitivity: nudge every knob under these prefixes")
    parser.add_argument(
        "--relative", type=float, default=DEFAULT_RELATIVE_STEP, help="sensitivity: nudge size"
    )
    parser.add_argument("--metrics", help="sensitivity: comma-separated metric columns")
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


def _split(text: str | None) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()] if text else []


def _run(
    runner: BalanceRunner, config: SimConfig, profile: Profile, arguments: argparse.Namespace
) -> int:
    results = evaluate(runner.run(config), profile.metrics)
    print(format_report(results, arguments.matches, profile.name))
    if arguments.failures and failures(results):
        print()
        print(format_failures(results))
    return EXIT_OFF_TARGET if failures(results) else EXIT_OK


def _chosen_knobs(config: SimConfig, arguments: argparse.Namespace) -> list[knobs.Knob]:
    if arguments.knobs:
        return knobs.choose(config, _split(arguments.knobs))
    found = knobs.discover(config)
    prefixes = tuple(f"{group}." for group in _split(arguments.group))
    if not prefixes:
        msg = "sensitivity needs --knobs or --group (for example --group shot,passing)"
        raise ValueError(msg)
    return [knob for knob in found if knob.path.startswith(prefixes)]


def _matrix_targets(profile: Profile, arguments: argparse.Namespace) -> dict[str, Target]:
    names = _split(arguments.metrics) or [m for m in MATRIX_METRICS if m in profile.metrics]
    unknown = [name for name in names if name not in profile.metrics]
    if unknown:
        msg = f"unknown metrics: {', '.join(unknown)}"
        raise ValueError(msg)
    return {name: profile.metrics[name] for name in names}


def _sensitivity(
    runner: BalanceRunner, config: SimConfig, profile: Profile, arguments: argparse.Namespace
) -> int:
    targets = _matrix_targets(profile, arguments)
    base = evaluate(runner.run(config), targets)
    found = sweep(runner.run, config, _chosen_knobs(config, arguments), targets, arguments.relative)
    print(f"profile {profile.name}, {arguments.matches} matches, nudge +-{arguments.relative:.0%}")
    print(format_matrix(found, list(targets), noise_floor(base)))
    for name in targets:
        top = ", ".join(
            f"{s.knob.path} {(s.effects or {})[name]:+.2f}"
            for s in strongest(found, name, STRONGEST_PER_METRIC)
        )
        print(f"moves {name}: {top}")
    return EXIT_OK


_HANDLERS: dict[str, Callable[[BalanceRunner, SimConfig, Profile, argparse.Namespace], int]] = {
    "run": _run,
    "sensitivity": _sensitivity,
}


def _execute(arguments: argparse.Namespace) -> int:
    config = load_config(arguments)
    profile = load_profile(arguments.profile)
    scenarios, sim_tables = open_scenarios(arguments)
    with BalanceRunner(scenarios, sim_tables, arguments.workers) as runner:
        return _HANDLERS[arguments.command](runner, config, profile, arguments)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the exit code (0 all PASS, 1 some metric misses, 2 usage)."""
    arguments = build_parser().parse_args(argv)
    try:
        return _execute(arguments)
    except (ValueError, ValidationError, StaticDataError, WorldFileError, OSError) as error:
        print(f"balance: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
