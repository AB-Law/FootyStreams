"""``uv run balance``: play many matches over a world and compare them with a balance profile.

A thin wrapper over the ``balance`` library. The world is loaded once and every ordered pairing of
its clubs is played in turn. Commands: ``run`` (the default) prints the targets table;
``sensitivity`` nudges knobs and prints which knob moves which metric; ``fit`` searches chosen
knobs for the lowest loss and writes a candidate config for review.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from footystreams.balance.runner import default_workers
from footystreams.balance.sensitivity import DEFAULT_RELATIVE_STEP, Sides
from footystreams.balance.targets import DEFAULT_PROFILE
from footystreams.cli.balance_commands import EXIT_OFF_TARGET, EXIT_OK, HANDLERS
from footystreams.cli.balance_session import open_session
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.world_io import WorldFileError
from footystreams.tools.paths import PROJECT_ROOT

DEFAULT_WORLD = PROJECT_ROOT / "data" / "worlds" / "default"
DEFAULT_MATCHES = 1200
DEFAULT_SEED = 1
DEFAULT_MAX_EVALUATIONS = 200
DEFAULT_VALIDATION_MATCHES = 600
EXIT_USAGE = 2

__all__ = ["EXIT_OFF_TARGET", "EXIT_OK", "EXIT_USAGE", "build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(prog="balance", description=__doc__)
    parser.add_argument("command", nargs="?", choices=sorted(HANDLERS), default="run")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="balance profile (realistic)")
    parser.add_argument("--matches", type=int, default=DEFAULT_MATCHES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="base seed of the run")
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD, help="world directory to play")
    parser.add_argument("--config", type=Path, help="partial SimConfig YAML laid over the defaults")
    parser.add_argument(
        "--set", action="append", default=[], dest="pairs", metavar="GROUP.KNOB=VALUE",
        help="override one knob (repeatable)",
    )  # fmt: skip
    parser.add_argument(
        "--min-gap", type=float, default=0.0, dest="min_gap",
        help="play only pairings whose rating gap is at least this (strength studies)",
    )  # fmt: skip
    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--failures", action="store_true", help="run: only the metrics that miss")
    parser.add_argument("--knobs", help="sensitivity, fit: comma-separated knob paths")
    parser.add_argument("--group", help="sensitivity, fit: every knob under these prefixes")
    parser.add_argument(
        "--relative", type=float, default=DEFAULT_RELATIVE_STEP, help="sensitivity: nudge size"
    )
    parser.add_argument("--metrics", help="sensitivity: comma-separated metric columns")
    parser.add_argument(
        "--sides", choices=[side.value for side in Sides], default=Sides.BOTH.value,
        help="sensitivity: nudge down and up (both) or only up (half the cost)",
    )  # fmt: skip
    parser.add_argument(
        "--state", type=Path, help="sensitivity: save progress here; resume if it exists"
    )
    parser.add_argument(
        "--report", type=Path, help="sensitivity: also write the table to this file"
    )
    parser.add_argument("--max-evals", type=int, default=DEFAULT_MAX_EVALUATIONS, dest="max_evals")
    parser.add_argument("--restarts", type=int, default=1, help="fit: searches to run")
    parser.add_argument("--bounds", help="fit: allowed multiplier range of each knob, low,high")
    parser.add_argument("--out", type=Path, help="fit: write the candidate config here")
    parser.add_argument(
        "--validation-matches", type=int, default=DEFAULT_VALIDATION_MATCHES,
        dest="validation_matches", help="fit: fresh matches that judge the candidate",
    )  # fmt: skip
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the exit code (0 ok, 1 some metric misses, 2 usage)."""
    arguments = build_parser().parse_args(argv)
    try:
        return HANDLERS[arguments.command](open_session(arguments))
    except (ValueError, ValidationError, StaticDataError, WorldFileError, OSError) as error:
        print(f"balance: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
