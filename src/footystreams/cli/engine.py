"""``uv run engine``: run the channel (thin wrapper over the runtime library).

It starts, plays the league forward a little ahead of the broadcast and airs it on the configured
pace to the configured sinks, until it is told to stop (SIGINT / SIGTERM / Ctrl-Break) or a finite
run (``--max-seasons`` / ``--until-date``) is done. The broadcast is NDJSON, one event per line, on
``--sink`` (default ``ndjson:stdout``); logs are JSON lines on stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from pydantic import ValidationError

from footystreams.cli.engine_wiring import make_engine, make_pool, prepare_database
from footystreams.cli.league_wiring import SimulatorKind
from footystreams.persistence.errors import PersistenceError
from footystreams.runtime.config import EngineConfig, parse_pace
from footystreams.runtime.engine import Engine, ExitReason
from footystreams.runtime.health import JsonFormatter
from footystreams.runtime.lock import AlreadyRunningError
from footystreams.runtime.sinks import STDOUT_SPEC, build_sinks
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.world_io import WorldFileError
from footystreams.tools.paths import PROJECT_ROOT

DEFAULT_WORLD = PROJECT_ROOT / "data" / "worlds" / "default"
EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(prog="engine", description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="SQLite database (created if new)")
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD, help="world to start a new db")
    parser.add_argument("--pace", default="realtime", help="realtime, scaled:N or instant")
    parser.add_argument(
        "--sink", action="append", dest="sinks", metavar="SPEC",
        help="ndjson:stdout (default), ndjson:file:PATH or memory; repeatable",
    )  # fmt: skip
    parser.add_argument("--max-seasons", type=int, dest="max_seasons")
    parser.add_argument("--until-date", type=dt.date.fromisoformat, dest="until_date")
    parser.add_argument("--buffer-matchdays", type=int, default=1, dest="buffer_matchdays")
    parser.add_argument("--cursor-every", type=int, default=25, dest="cursor_every")
    parser.add_argument(
        "--starve-grace-s", type=float, default=30.0, dest="starve_grace_s",
        help="real seconds to wait for the next matchday before airing filler",
    )  # fmt: skip
    parser.add_argument("--safe-mode", action="store_true", dest="safe_mode")
    parser.add_argument(
        "--simulator", type=SimulatorKind, choices=list(SimulatorKind), default=SimulatorKind.EVENT
    )
    parser.add_argument("--log-level", default="WARNING", dest="log_level")
    return parser


def config_from(arguments: argparse.Namespace) -> EngineConfig:
    """The validated engine settings for the command line."""
    return EngineConfig(
        db_path=arguments.db,
        pace=parse_pace(arguments.pace),
        sinks=tuple(arguments.sinks or [STDOUT_SPEC]),
        max_seasons=arguments.max_seasons,
        until_date=arguments.until_date,
        buffer_matchdays=arguments.buffer_matchdays,
        cursor_every=arguments.cursor_every,
        starve_grace_s=arguments.starve_grace_s,
        safe_mode=arguments.safe_mode,
    )


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)


def _stop_on_signals(engine: Engine) -> None:
    def request_stop(_signal: int, _frame: FrameType | None) -> None:
        engine.request_stop()

    names = ("SIGINT", "SIGTERM", "SIGBREAK")  # SIGBREAK is Ctrl-Break, Windows only
    for name in names:
        number = getattr(signal, name, None)
        if number is not None:
            signal.signal(number, request_stop)


def _run(arguments: argparse.Namespace) -> int:
    config = config_from(arguments)
    prepare_database(config.db_path, arguments.world)
    sinks = build_sinks(config.sinks)
    with make_pool(config.db_path, arguments.simulator) as pool:
        engine = make_engine(config, sinks, pool)
        _stop_on_signals(engine)
        reason = asyncio.run(engine.run())
    return EXIT_FAILED if reason is ExitReason.FAILED else EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the exit code (0 finished or stopped, 1 failed, 2 usage)."""
    arguments = build_parser().parse_args(argv)
    _configure_logging(arguments.log_level)
    try:
        return _run(arguments)
    except (
        ValueError,
        ValidationError,
        StaticDataError,
        WorldFileError,
        PersistenceError,
        AlreadyRunningError,
        OSError,
    ) as error:
        print(f"engine: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
