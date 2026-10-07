"""`uv run sim`: simulate one match and print a readable play-by-play and summary.

A thin wrapper over `run_match`: all logic lives in the library. Until a world exists the match is
played between position-aware demo teams from `tests/factories` (`--demo`); loading clubs from a
world (`--home`, `--away`, `--world`/`--db`) arrives when the world track merges.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence
from enum import StrEnum

from footystreams.cli.render import Verbosity, names_for, render_events, render_summary
from footystreams.domain.match import MatchSetup
from footystreams.sim import SimConfig, default_tables, run_match
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
    parser.add_argument("--home-strength", type=int, default=DEFAULT_STRENGTH)
    parser.add_argument("--away-strength", type=int, default=DEFAULT_STRENGTH)
    parser.add_argument("--home-formation", default="433")
    parser.add_argument("--away-formation", default="433")
    for option in ("--home", "--away", "--world", "--db"):
        parser.add_argument(option, help="needs a generated world (not available yet)")
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the process exit code."""
    arguments = build_parser().parse_args(argv)
    if not arguments.demo:
        print(
            "error: pass --demo (clubs from a world need the seed/persistence tracks)",
            file=sys.stderr,
        )
        return EXIT_USAGE
    setup = _demo_setup(arguments)
    result = run_match(setup, arguments.seed, SimConfig(), default_tables())
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
