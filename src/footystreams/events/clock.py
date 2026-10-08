"""Conversions between playing seconds and the displayed `MatchClock`.

The clock shows regulation minutes and then stoppage minutes: a goal 2 min 10 s into added time
in the first half is `minute=45, stoppage=2, second=10`. Periods 3 and 4 are reserved for extra
time. Pure helpers; they do not change the event schema.
"""

from __future__ import annotations

from footystreams.events.base import MatchClock

SECONDS_PER_MINUTE = 60
PERIOD_LENGTH_S = (2700, 2700, 900, 900)
PERIOD_START_MINUTE = (0, 45, 90, 105)


def match_clock(period: int, elapsed_s: int) -> MatchClock:
    """Return the displayed clock `elapsed_s` seconds into `period` (1-4)."""
    length = PERIOD_LENGTH_S[period - 1]
    start = PERIOD_START_MINUTE[period - 1]
    if elapsed_s < length:
        minute, stoppage = start + elapsed_s // SECONDS_PER_MINUTE, 0
    else:
        minute = start + length // SECONDS_PER_MINUTE
        stoppage = (elapsed_s - length) // SECONDS_PER_MINUTE
    return MatchClock(
        period=period, minute=minute, second=elapsed_s % SECONDS_PER_MINUTE, stoppage=stoppage
    )


def period_elapsed_s(clock: MatchClock) -> int:
    """Return the seconds into the period that a displayed clock stands for (inverse of above)."""
    start = PERIOD_START_MINUTE[clock.period - 1]
    return (clock.minute - start + clock.stoppage) * SECONDS_PER_MINUTE + clock.second


def match_elapsed_s(clock: MatchClock) -> int:
    """Return playing seconds since kick-off (half-time excluded) for a displayed clock."""
    before = sum(PERIOD_LENGTH_S[: clock.period - 1])
    return before + period_elapsed_s(clock)
