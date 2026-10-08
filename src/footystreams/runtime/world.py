"""``WorldStepper``: one in-world day at a time, for the simulation buffer.

Each call schedules the current season's fixtures if it has none yet (a new season after the
rollover) and then runs the league's daily tick. On the day after a season ends there is no
current season until the rollover stage has made the next one, so a missing season simply means
"run the day". The tick is idempotent through the stage log, so a crash mid-day repeats nothing.
"""

from __future__ import annotations

from footystreams.league.clock import read_date
from footystreams.league.daily import DayReport
from footystreams.league.season import SeasonRunner, current_season
from footystreams.persistence.errors import NotFoundError
from footystreams.persistence.ports import UnitOfWorkFactory


class WorldStepper:
    """Callable that plays the next in-world day and reports what it did."""

    def __init__(self, runner: SeasonRunner, factory: UnitOfWorkFactory) -> None:
        """Wrap a season runner over the same database."""
        self._runner = runner
        self._factory = factory

    def __call__(self) -> DayReport:
        """Prepare the current season if needed, then run one day."""
        with self._factory() as uow:
            try:
                season = current_season(uow, read_date(uow))
            except NotFoundError:
                season = None  # between seasons: the rollover stage creates the next one
        if season is not None:
            self._runner.prepare(season)
        return self._runner.run_day()
