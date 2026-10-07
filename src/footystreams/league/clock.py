"""``WorldClock``: the in-world date, kept in ``world_meta`` and advanced one day at a time."""

from __future__ import annotations

import datetime as dt

from footystreams.persistence.ports import MetaEntry, Repositories, UnitOfWorkFactory

KEY_CURRENT_DATE = "current_date"
ONE_DAY = dt.timedelta(days=1)


def read_date(repositories: Repositories) -> dt.date:
    """The in-world date stored in the database."""
    entry = repositories.meta.require(KEY_CURRENT_DATE)
    return dt.date.fromisoformat(entry.value)


def write_date(repositories: Repositories, date: dt.date) -> None:
    """Store the in-world date (the caller commits)."""
    repositories.meta.save(MetaEntry(key=KEY_CURRENT_DATE, value=date.isoformat()))


class WorldClock:
    """Reads and advances the world's date; nothing else in the league layer moves time."""

    def __init__(self, factory: UnitOfWorkFactory) -> None:
        """Create a clock over a database."""
        self._factory = factory

    def current_date(self) -> dt.date:
        """The current in-world date."""
        with self._factory() as uow:
            return read_date(uow)

    def advance_day(self) -> dt.date:
        """Move to the next day (one transaction) and return it."""
        with self._factory() as uow:
            tomorrow = read_date(uow) + ONE_DAY
            write_date(uow, tomorrow)
            uow.commit()
        return tomorrow
