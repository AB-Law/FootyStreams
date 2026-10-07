"""In-world dates: matchdays, transfer windows and the contract end day (pure functions)."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.transfer import WindowKind
from footystreams.league.config import CalendarConfig


def matchday_dates(calendar: CalendarConfig, start: dt.date, matchdays: int) -> list[dt.date]:
    """One date per matchday, evenly spaced from the season's first day."""
    return [
        start + dt.timedelta(days=calendar.matchday_spacing_days * index)
        for index in range(matchdays)
    ]


def window_dates(
    calendar: CalendarConfig, kind: WindowKind, season_start: dt.date, matchdays: list[dt.date]
) -> tuple[dt.date, dt.date]:
    """Opening and closing dates of a transfer window of the season starting at ``season_start``."""
    if kind is WindowKind.MIDSEASON:
        opens = matchdays[calendar.midseason_window_after_matchday - 1] + dt.timedelta(days=1)
        return opens, opens + dt.timedelta(days=calendar.midseason_window_days - 1)
    year = season_start.year + 1  # the summer window that ends this season's off-season
    return (
        dt.date(year, *calendar.summer_window_open),
        dt.date(year, *calendar.summer_window_close),
    )


def contract_end_after(calendar: CalendarConfig, today: dt.date) -> dt.date:
    """The next contract-end day strictly after ``today``."""
    candidate = dt.date(today.year, *calendar.contract_end)
    return candidate if candidate > today else dt.date(today.year + 1, *calendar.contract_end)
