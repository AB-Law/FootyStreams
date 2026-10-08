"""``uv run seed``: generate, validate and write a world (thin wrapper over the seed library)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from footystreams.cli.world_checks import build_world_checks, build_world_targets
from footystreams.domain.world import World
from footystreams.seed.config import MAX_CLUBS, GeneratorConfig
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.static.tables import StaticTables, load_static_tables
from footystreams.seed.world_gen import generate_world
from footystreams.seed.world_io import WorldFileError, read_world, write_world
from footystreams.tools.paths import PROJECT_ROOT
from footystreams.verify import format_violations, verify_world

DEFAULT_SEED = 1
WORLDS_DIRECTORY = PROJECT_ROOT / "data" / "worlds"
EXIT_OK, EXIT_VIOLATIONS, EXIT_USAGE = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seed", description="Generate a fictional football world")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="world seed (default 1)")
    parser.add_argument("--clubs", type=int, default=MAX_CLUBS, help="number of clubs (2-8)")
    parser.add_argument("--name", help="world name (default: seed-<N>)")
    parser.add_argument("--out", type=Path, help="output directory (default: data/worlds/<name>)")
    parser.add_argument(
        "--validate", action="store_true", help="run only the coherence checks; write nothing"
    )
    parser.add_argument("--world", type=Path, help="with --validate: check this existing world")
    return parser


def _report(world: World, tables: StaticTables) -> int:
    violations = verify_world(world, build_world_checks(tables), build_world_targets(tables))
    if violations:
        print(f"coherence checks: FAIL ({len(violations)} violations)")
        print(format_violations(violations))
        return EXIT_VIOLATIONS
    print("coherence checks: PASS (0 violations)")
    return EXIT_OK


def _run(arguments: argparse.Namespace) -> int:
    tables = load_static_tables()
    if arguments.validate and arguments.world is not None:
        return _report(read_world(arguments.world), tables)
    world = generate_world(arguments.seed, GeneratorConfig(clubs=arguments.clubs), tables)
    status = _report(world, tables)
    if arguments.validate or status != EXIT_OK:
        return status
    name = arguments.name or f"seed-{arguments.seed}"
    destination = arguments.out or WORLDS_DIRECTORY / name
    manifest = write_world(world, destination)
    print(f"wrote {destination} ({len(world.players)} players, {len(world.clubs)} clubs)")
    print(f"content_sha256={manifest.content_sha256}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code (0 ok, 1 violations, 2 usage or I/O error)."""
    arguments = _parser().parse_args(argv)
    try:
        return _run(arguments)
    except (ValueError, WorldFileError, StaticDataError) as error:
        print(f"seed: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
