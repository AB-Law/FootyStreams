"""The metrics of docs/design/02 section 14.1: each is a pure function of a list of samples.

A metric returns ``nan`` when it is undefined for the sample (a ratio with nothing under the line);
the report shows that as "n/a" and counts it as a failure, so a broken run cannot pass quietly.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from statistics import fmean, pstdev

from footystreams.balance.metrics_strength import STRENGTH_METRICS
from footystreams.balance.sample import MatchSample, SideSample

Metric = Callable[[Sequence[MatchSample]], float]
MatchValue = Callable[[MatchSample], float]

PERCENT = 100.0
BIG_SCORELINE_GOALS = 5
TEAMS = 2


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else math.nan


def _mean(value: MatchValue) -> Metric:
    """The mean of a per-match value."""
    return lambda samples: fmean(value(sample) for sample in samples) if samples else math.nan


def _percent(condition: Callable[[MatchSample], bool]) -> Metric:
    """The percentage of matches meeting a condition."""
    return _mean(lambda sample: PERCENT if condition(sample) else 0.0)


def _both_sides(field: Callable[[SideSample], float]) -> MatchValue:
    return lambda sample: field(sample.home) + field(sample.away)


def _per_team(field: Callable[[SideSample], float]) -> Metric:
    """The mean of a team figure over all team-matches."""
    return _mean(lambda sample: _both_sides(field)(sample) / TEAMS)


def _sum_ratio(numerator: MatchValue, denominator: MatchValue) -> Metric:
    """Total numerator over total denominator (a ratio of sums, not a mean of ratios)."""
    return lambda samples: _ratio(
        sum(numerator(sample) for sample in samples),
        sum(denominator(sample) for sample in samples),
    )


def _possession_spread(samples: Sequence[MatchSample]) -> float:
    """Standard deviation across matches of the home side's possession, in percentage points."""
    return pstdev(sample.home.possession * PERCENT for sample in samples) if samples else math.nan


def _goal_share(part: MatchValue) -> Metric:
    return _sum_ratio(lambda sample: part(sample) * PERCENT, lambda sample: sample.goals)


def _a_team_scored(minimum: int) -> Callable[[MatchSample], bool]:
    return lambda sample: max(sample.home.goals, sample.away.goals) >= minimum


_SHOTS = _both_sides(lambda team: team.shots)

GENERAL_METRICS: dict[str, Metric] = {
    "goals_per_match": _mean(lambda s: s.goals),
    "home_goals_per_match": _mean(lambda s: s.home.goals),
    "away_goals_per_match": _mean(lambda s: s.away.goals),
    "home_goal_share_pct": _goal_share(lambda s: s.home.goals),
    "home_win_pct": _percent(lambda s: s.home.goals > s.away.goals),
    "draw_pct": _percent(lambda s: s.home.goals == s.away.goals),
    "away_win_pct": _percent(lambda s: s.home.goals < s.away.goals),
    "scoreless_pct": _percent(lambda s: s.goals == 0),
    "five_plus_goals_pct": _percent(lambda s: s.goals >= BIG_SCORELINE_GOALS),
    "team_five_plus_pct": _percent(_a_team_scored(BIG_SCORELINE_GOALS)),
    "second_half_goal_share_pct": _goal_share(lambda s: s.goals_second_half),
    "late_goal_share_pct": _goal_share(lambda s: s.goals_late),
    "shots_per_team": _per_team(lambda t: t.shots),
    "on_target_per_shot": _sum_ratio(_both_sides(lambda t: t.on_target), _SHOTS),
    "goals_per_shot_pct": _sum_ratio(lambda s: s.goals * PERCENT, _SHOTS),
    "pass_completion_pct": _sum_ratio(
        _both_sides(lambda t: t.passes_completed * PERCENT), _both_sides(lambda t: t.passes)
    ),
    "possession_spread_pp": _possession_spread,
    "corners_per_match": _mean(_both_sides(lambda t: t.corners)),
    "offsides_per_match": _mean(_both_sides(lambda t: t.offsides)),
    "fouls_per_match": _mean(_both_sides(lambda t: t.fouls)),
    "yellows_per_match": _mean(_both_sides(lambda t: t.yellows)),
    "reds_per_match": _mean(_both_sides(lambda t: t.reds)),
    "penalties_per_match": _mean(lambda s: s.penalties),
    "penalty_conversion_pct": _sum_ratio(
        lambda s: s.penalties_scored * PERCENT, lambda s: s.penalties
    ),
    "injuries_per_match": _mean(lambda s: s.injuries),
    "substitutions_per_team": _per_team(lambda t: t.substitutions),
    "early_tactical_subs_per_match": _mean(lambda s: s.early_tactical_subs),
    "added_time_first_half_min": _mean(lambda s: s.added_first_half),
    "added_time_second_half_min": _mean(lambda s: s.added_second_half),
}

METRICS: dict[str, Metric] = {**GENERAL_METRICS, **STRENGTH_METRICS}
