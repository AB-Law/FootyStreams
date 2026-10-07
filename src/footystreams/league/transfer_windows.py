"""Transfer windows: when they are open, computed from the calendar (pure)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.competition import Season
from footystreams.domain.ids import derive_id
from footystreams.domain.transfer import TransferWindow, WindowKind
from footystreams.domain.types import Id, SeasonId
from footystreams.league.calendar import matchday_dates, window_dates
from footystreams.league.config import CalendarConfig


def windows_for(season: Season, calendar: CalendarConfig) -> list[TransferWindow]:
    """The summer window before the season and the mid-season window within it.

    The summer window opens on the configured day but never before the season's year starts being
    relevant: it runs up to the season opener. The mid-season window follows the configured
    matchday.
    """
    start = season.starts_on
    summer_opens = dt.date(start.year, *calendar.summer_window_open)
    summer_closes = dt.date(start.year, *calendar.summer_window_close)
    dates = matchday_dates(calendar, start, season.matchdays)
    mid_opens, mid_closes = window_dates(calendar, WindowKind.MIDSEASON, start, dates)
    return [
        _window(season.id, WindowKind.SUMMER, summer_opens, summer_closes),
        _window(season.id, WindowKind.MIDSEASON, mid_opens, mid_closes),
    ]


def _window(
    season_id: SeasonId, kind: WindowKind, opens: dt.date, closes: dt.date
) -> TransferWindow:
    return TransferWindow(
        id=Id(derive_id("window", season_id, kind.value)),
        season_id=season_id,
        kind=kind,
        opens_on=opens,
        closes_on=closes,
    )


def open_window(windows: Sequence[TransferWindow], today: dt.date) -> TransferWindow | None:
    """The window open on ``today`` (the earliest if two overlapped), or None."""
    live = [w for w in windows if w.opens_on <= today <= w.closes_on]
    return min(live, key=lambda w: (w.opens_on, w.id), default=None)


def days_left(window: TransferWindow, today: dt.date) -> int:
    """Days until the window closes; 0 on its last day."""
    return (window.closes_on - today).days
