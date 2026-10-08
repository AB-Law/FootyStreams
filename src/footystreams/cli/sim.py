"""`uv run sim`: simulate one match and print a readable play-by-play and summary.

A thin wrapper over `run_match`: all logic lives in the library. The match is played either between
position-aware demo teams from `tests/factories` (`--demo`) or as a friendly between two clubs of a
world (`--home A --away B` with `--world DIR` or `--db FILE`; a club is its id, short code or name).
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from footystreams.cli.sim_world import resolve_world_match
from footystreams.domain.match import MatchSetup
from footystreams.domain.referee import Referee
from footystreams.persistence.ports import NotFoundError
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.world_io import WorldFileError
from footystreams.sim import SimConfig, default_tables, run_match
from footystreams.sim.render import Verbosity, names_for, render_events, render_summary
from footystreams.sim.tables import StaticTables
from footystreams.tools.paths import PROJECT_ROOT

DEFAULT_STRENGTH = 62
EXIT_USAGE = 2


class OutputFormat(StrEnum):
    """Output encodings."""

    TEXT = "text"
    NDJSON = "ndjson"


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(prog="sim", description=__doc__)
    parser.add_argument("--demo", action="store_true", help="play between demo teams")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--format", type=OutputFormat, choices=list(OutputFormat), default="text")
    parser.add_argument("--verbosity", type=Verbosity, choices=list(Verbosity), default="key")
    parser.add_argument("--frames", action="store_true", help="emit tracking frames (ndjson only)")
    parser.add_argument("--frame-interval", type=int, default=1, help="seconds between frames")
    parser.add_argument("--home-strength", type=int, default=DEFAULT_STRENGTH)
    parser.add_argument("--away-strength", type=int, default=DEFAULT_STRENGTH)
    parser.add_argument("--home-formation", default="433")
    parser.add_argument("--away-formation", default="433")
    parser.add_argument("--home", help="home club of a world: id, short code or name")
    parser.add_argument("--away", help="away club of a world: id, short code or name")
    parser.add_argument("--world", type=Path, help="world directory to take the clubs from")
    parser.add_argument("--db", type=Path, help="SQLite database to take the clubs from")
    return parser


def _demo_setup(arguments: argparse.Namespace) -> MatchSetup:
    """Build the demo setup; the factories live in the source checkout, not the package."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    factory = importlib.import_module("tests.factories.sim_teams")
    setup: MatchSetup = factory.make_demo_setup(
        home_strength=arguments.home_strength,
        away_strength=arguments.away_strength,
        home_formation=arguments.home_formation,
        away_formation=arguments.away_formation,
    )
    return setup


def _resolve(arguments: argparse.Namespace) -> tuple[MatchSetup, StaticTables, Referee | None]:
    """The setup, the tables to play it with and its referee (the demo has none)."""
    if arguments.demo:
        return _demo_setup(arguments), default_tables(), None
    found = resolve_world_match(arguments)
    return found.setup, found.tables, found.referee


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the process exit code."""
    arguments = build_parser().parse_args(argv)
    try:
        setup, tables, referee = _resolve(arguments)
    except (ValueError, NotFoundError, WorldFileError, StaticDataError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    config = SimConfig(emit_frames=arguments.frames, frame_interval_s=arguments.frame_interval)
    result = run_match(setup, arguments.seed, config, tables, referee)
    if arguments.format is OutputFormat.NDJSON:
        for event in result.events:
            print(event.model_dump_json())
        return 0
    names = names_for(setup)
    for line in render_events(result.events, names, arguments.verbosity):
        print(line)
    print()
    for line in render_summary(result.summary, names):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
