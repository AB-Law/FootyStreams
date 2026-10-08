"""Strength and upset metrics (docs/design/02 section 14.2).

A match belongs to a gap bin by the size of the rating difference between its teams, whichever
side is home; the favourite is the higher-rated side. Each bin yields three percentages.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from itertools import pairwise
from statistics import fmean

from footystreams.balance.sample import MatchSample

PERCENT = 100.0
# (name, lower bound inclusive, upper bound exclusive) on |rating gap|.
GAP_BINS: tuple[tuple[str, float, float], ...] = (
    ("even", 0.0, 3.0),
    ("small", 3.0, 8.0),
    ("medium", 8.0, 15.0),
    ("large", 15.0, math.inf),
)
EDGE_FROM_GAP = 3.0  # below this there is no favourite, so no home or away favourite

Metric = Callable[[Sequence[MatchSample]], float]
Outcome = Callable[[MatchSample], bool]


def _favourite_goals(sample: MatchSample) -> tuple[int, int]:
    """(favourite goals, underdog goals); the home side is favourite when the gap is positive."""
    if sample.gap >= 0:
        return sample.home.goals, sample.away.goals
    return sample.away.goals, sample.home.goals


def _favourite_won(sample: MatchSample) -> bool:
    favourite, underdog = _favourite_goals(sample)
    return favourite > underdog


def _drawn(sample: MatchSample) -> bool:
    favourite, underdog = _favourite_goals(sample)
    return favourite == underdog


def _underdog_won(sample: MatchSample) -> bool:
    favourite, underdog = _favourite_goals(sample)
    return favourite < underdog


def _in_bin(samples: Sequence[MatchSample], low: float, high: float) -> list[MatchSample]:
    return [s for s in samples if low <= abs(s.gap) < high]


def _bin_metric(low: float, high: float, outcome: Outcome) -> Metric:
    def metric(samples: Sequence[MatchSample]) -> float:
        chosen = _in_bin(samples, low, high)
        if not chosen:
            return math.nan
        return fmean(PERCENT if outcome(s) else 0.0 for s in chosen)

    return metric


def _favourite_rate(samples: Sequence[MatchSample], *, home: bool) -> float:
    chosen = [s for s in samples if abs(s.gap) >= EDGE_FROM_GAP and (s.gap > 0) == home]
    if not chosen:
        return math.nan
    return fmean(PERCENT if _favourite_won(s) else 0.0 for s in chosen)


def home_favourite_edge_pp(samples: Sequence[MatchSample]) -> float:
    """How much more often a home favourite wins than an away favourite (percentage points)."""
    return _favourite_rate(samples, home=True) - _favourite_rate(samples, home=False)


def favourite_win_rises_with_gap(samples: Sequence[MatchSample]) -> float:
    """1 when the favourite's win rate is strictly higher in every wider bin, else 0."""
    rates = [_bin_metric(low, high, _favourite_won)(samples) for _, low, high in GAP_BINS]
    if any(math.isnan(rate) for rate in rates):
        return math.nan
    return 1.0 if all(a < b for a, b in pairwise(rates)) else 0.0


def _bin_metrics() -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    for name, low, high in GAP_BINS:
        metrics[f"favourite_win_pct_{name}"] = _bin_metric(low, high, _favourite_won)
        metrics[f"draw_pct_{name}"] = _bin_metric(low, high, _drawn)
        metrics[f"underdog_win_pct_{name}"] = _bin_metric(low, high, _underdog_won)
    return metrics


STRENGTH_METRICS: dict[str, Metric] = {
    **_bin_metrics(),
    "home_favourite_edge_pp": home_favourite_edge_pp,
    "favourite_win_rises_with_gap": favourite_win_rises_with_gap,
}
