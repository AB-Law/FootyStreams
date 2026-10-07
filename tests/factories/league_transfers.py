"""Transfer-market scenarios: a market loaded from a seed world and runs to a window's end."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.rng import WorldRng
from footystreams.domain.transfer import TransferWindow
from footystreams.league.clock import WorldClock
from footystreams.league.delta import WorldDelta
from footystreams.league.season import SeasonRunner
from footystreams.league.transfer_data import run_window_day
from footystreams.league.transfer_windows import windows_for
from footystreams.persistence.ports import UnitOfWorkFactory
from tests.factories.league_inputs import make_league_tables
from tests.factories.league_run import make_multi_runner, make_prospects


def first_window(factory: UnitOfWorkFactory) -> TransferWindow:
    """The summer window before the first season."""
    tables = make_league_tables()
    with factory() as uow:
        season = uow.seasons.all()[0]
    return windows_for(season, tables.config.calendar)[0]


def window_delta(
    factory: UnitOfWorkFactory, day: dt.date, seed: int = 1, clubs: int = 4
) -> WorldDelta:
    """What the transfer stage would write on ``day`` of the first summer window."""
    with factory() as uow:
        return run_window_day(
            uow,
            first_window(factory),
            (day, make_league_tables(), make_prospects(seed, clubs)),
            WorldRng(5),
        )


def run_until(runner: SeasonRunner, date: dt.date, factory: UnitOfWorkFactory) -> None:
    """Step the runner day by day until the world clock reads ``date``."""
    clock = WorldClock(factory)
    while clock.current_date() < date:
        runner.run_day()


def runner_for(seed: int = 2, clubs: int = 4) -> tuple[SeasonRunner, UnitOfWorkFactory]:
    """A fresh runner with the rollover and the market enabled."""
    return make_multi_runner(seed, clubs)
