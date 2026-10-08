"""Behavioural sanity over league-sized samples (docs/design/02 section 14.4)."""

from __future__ import annotations

from statistics import fmean

import pytest

from footystreams.balance.sample import MatchSample
from footystreams.cli.balance import build_parser
from footystreams.cli.balance_session import open_session

MATCHES = 400
WIN_POINTS, DRAW_POINTS = 3, 1


def _samples() -> list[MatchSample]:
    arguments = build_parser().parse_args(["--matches", str(MATCHES), "--workers", "4"])
    session = open_session(arguments)
    with session.runner() as runner:
        return runner.run(session.config)


def _points(scored: int, conceded: int) -> int:
    if scored > conceded:
        return WIN_POINTS
    return DRAW_POINTS if scored == conceded else 0


def _team_points(samples: list[MatchSample], *, sent_off: bool) -> float:
    """Mean points of the teams that did (or did not) have a player sent off."""
    points = []
    for sample in samples:
        for team, other in ((sample.home, sample.away), (sample.away, sample.home)):
            if (team.reds > 0) is sent_off:
                points.append(_points(team.goals, other.goals))
    return fmean(points)


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(900)
def test_red_card__a_team_that_is_sent_off_earns_fewer_points_than_one_that_is_not() -> None:
    samples = _samples()

    assert _team_points(samples, sent_off=True) < _team_points(samples, sent_off=False)


@pytest.mark.xfail(
    strict=True,
    reason="known M8 gap: the second half has fewer goals than the first (shots dip at 60-75 min)",
)
@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(900)
def test_goal_timing__more_goals_come_after_the_break_than_before_it() -> None:
    samples = _samples()

    second_half = sum(s.goals_second_half for s in samples)
    first_half = sum(s.goals for s in samples) - second_half

    assert second_half > first_half
