"""Added time: turn the stoppage of a period into the minutes the board shows.

`added = ceil(generosity x stoppage_minutes x 0.65)`, clamped per half, with the referee's
generosity scaling it between 0.7x and 1.3x (docs/design/02 section 12). Pure functions.
"""

from __future__ import annotations

from math import ceil

from footystreams.sim.config_rules import StoppageConfig
from footystreams.sim.mathx import clamp

SECONDS_PER_MINUTE = 60.0
FIRST_PERIOD = 1


def added_minutes(stoppage_s: float, generosity: float, period: int, cfg: StoppageConfig) -> int:
    """Return the announced added minutes for a period (period 1 clamps differently from 2)."""
    factor = cfg.generosity_base + cfg.generosity_swing * generosity
    raw = ceil(factor * (stoppage_s / SECONDS_PER_MINUTE) * cfg.minutes_per_stoppage)
    low, high = (
        (cfg.first_half_min, cfg.first_half_max)
        if period == FIRST_PERIOD
        else (cfg.second_half_min, cfg.second_half_max)
    )
    return int(clamp(raw, low, high))
