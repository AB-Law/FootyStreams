"""``uv run league``: run a seeded world through a season (thin wrapper over the league library)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine

from footystreams.cli.league_wiring import build_engine, build_prospects, load_league_tables
from footystreams.domain.competition import Season
from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.domain.types import ClubId, PlayerId
from footystreams.domain.world import World
from footystreams.league.clock import read_date
from footystreams.league.report import format_money, format_table, format_transfers
from footystreams.league.season import SeasonResult, SeasonRunner, current_season
from footystreams.persistence.memory_impl import InMemoryDatabase, InMemoryUnitOfWork
from footystreams.persistence.ports import NotFoundError, UnitOfWork, UnitOfWorkFactory
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.migrate import upgrade
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import KEY_WORLD_SEED, read_meta, save_world
from footystreams.seed.config import MAX_CLUBS, GeneratorConfig
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.static.tables import load_static_tables
from footystreams.seed.world_gen import generate_world
from footystreams.seed.world_io import WorldFileError, read_world

DEFAULT_SEED = 1
EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="league", description="Run a fictional football season")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="world seed (default 1)")
    parser.add_argument("--clubs", type=int, default=MAX_CLUBS, help="number of clubs (2-8)")
    parser.add_argument("--world", type=Path, help="start from this world directory, not --seed")
    parser.add_argument("--db", type=Path, help="SQLite file: resumed if it holds a world")
    parser.add_argument("--matchday", type=int, help="stop after this matchday has been played")
    parser.add_argument(
        "--seasons", type=int, help="play this many seasons, with the off-season between them"
    )
    parser.add_argument(
        "--transfers",
        action="store_true",
        help="print every completed transfer (the market always runs with --seasons)",
    )
    parser.add_argument(
        "--season-only", action="store_true", help="play the current season to its end (default)"
    )
    return parser


def _has_world(factory: UnitOfWorkFactory) -> bool:
    with factory() as uow:
        try:
            read_meta(uow, KEY_WORLD_SEED)
        except NotFoundError:
            return False
        return True


def _initial_world(arguments: argparse.Namespace) -> World:
    if arguments.world is not None:
        return read_world(arguments.world)
    return generate_world(
        arguments.seed, GeneratorConfig(clubs=arguments.clubs), load_static_tables()
    )


def _open(arguments: argparse.Namespace) -> tuple[UnitOfWorkFactory, Engine | None]:
    """The database to run on; a new one is filled with the starting world."""
    if arguments.db is None:
        database = InMemoryDatabase()

        def memory() -> UnitOfWork:
            return InMemoryUnitOfWork(database)

        save_world(_initial_world(arguments), memory())
        return memory, None
    engine = create_sqlite_engine(arguments.db)
    upgrade(engine)

    def sql() -> UnitOfWork:
        return SqlUnitOfWork(engine)

    if not _has_world(sql):
        save_world(_initial_world(arguments), sql())
    return sql, engine


def _print_transfers(factory: UnitOfWorkFactory) -> None:
    with factory() as uow:
        transfers = uow.transfers.all()
        names = {club.id: club.name for club in uow.clubs.all()}
        players = {PlayerId(p.id): p.known_as for p in uow.players.all()}
    print()
    print(format_transfers(transfers, names, players))


def _print_results(
    results: list[SeasonResult],
    factory: UnitOfWorkFactory,
    opening: dict[ClubId, int],
    *,
    show_transfers: bool,
) -> None:
    with factory() as uow:
        clubs = [club for club in uow.clubs.all() if club.id != OUTSIDE_WORLD]
        today = read_date(uow)
    names = {club.id: club.name for club in clubs}
    for result in results:
        print(f"{result.season.label}: {result.matches_played} matches played")
        print(format_table(result.table, names))
        print()
    print(f"now {today}")
    print(format_money(clubs, opening))
    if show_transfers:
        _print_transfers(factory)


def _play(
    arguments: argparse.Namespace, runner: SeasonRunner, season: Season
) -> list[SeasonResult]:
    if arguments.seasons is not None:
        return runner.run_seasons(arguments.seasons)
    if arguments.matchday is not None:
        return [runner.run_until_matchday(season, arguments.matchday)]
    return [runner.run_season(season)]


def _run(arguments: argparse.Namespace) -> int:
    factory, engine = _open(arguments)
    try:
        static = load_static_tables()
        with factory() as uow:
            world_seed = int(read_meta(uow, KEY_WORLD_SEED))
            season = current_season(uow, read_date(uow))
            opening = {
                club.id: club.finances.balance
                for club in uow.clubs.all()
                if club.id != OUTSIDE_WORLD
            }
            prospects = build_prospects(uow, static)
        runner = SeasonRunner(
            factory, build_engine(load_league_tables(static=static), world_seed), prospects
        )
        _print_results(
            _play(arguments, runner, season), factory, opening, show_transfers=arguments.transfers
        )
    finally:
        if engine is not None:
            engine.dispose()
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code (0 ok, 1 failed run, 2 usage or I/O error)."""
    arguments = _parser().parse_args(argv)
    try:
        return _run(arguments)
    except (ValueError, WorldFileError, StaticDataError, NotFoundError) as error:
        print(f"league: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
