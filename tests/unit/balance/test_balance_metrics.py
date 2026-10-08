from __future__ import annotations

import math

import pytest

from footystreams.balance.metrics import METRICS
from footystreams.balance.sample import MatchSample
from tests.factories.balance import make_sample, make_side


def _scored(home: int, away: int, **changes: float) -> MatchSample:
    return make_sample(make_side(goals=home), make_side(goals=away), **changes)


def test_goals_per_match__is_the_mean_of_both_teams_goals() -> None:
    samples = [_scored(2, 1), _scored(0, 0), _scored(1, 2)]

    assert METRICS["goals_per_match"](samples) == pytest.approx(2.0)


def test_results__home_draw_and_away_percentages_add_up_to_one_hundred() -> None:
    samples = [_scored(2, 1), _scored(0, 0), _scored(1, 2), _scored(3, 0)]

    shares = [METRICS[name](samples) for name in ("home_win_pct", "draw_pct", "away_win_pct")]

    assert shares == [50.0, 25.0, 25.0]


def test_scorelines__scoreless_and_five_plus_and_a_team_with_five() -> None:
    samples = [_scored(0, 0), _scored(5, 0), _scored(3, 2), _scored(1, 1)]

    assert METRICS["scoreless_pct"](samples) == 25.0
    assert METRICS["five_plus_goals_pct"](samples) == 50.0
    assert METRICS["team_five_plus_pct"](samples) == 25.0


def test_goal_timing__shares_are_of_all_goals_not_of_matches() -> None:
    samples = [
        _scored(2, 2, goals_second_half=3, goals_late=1),
        _scored(0, 0, goals_second_half=0),
    ]

    assert METRICS["second_half_goal_share_pct"](samples) == 75.0
    assert METRICS["late_goal_share_pct"](samples) == 25.0


def test_shots_per_team__averages_over_team_matches() -> None:
    sample = make_sample(make_side(shots=10), make_side(shots=16))

    assert METRICS["shots_per_team"]([sample]) == 13.0


def test_pass_completion__is_total_completed_over_total_passes() -> None:
    sample = make_sample(
        make_side(passes=100, passes_completed=90.0), make_side(passes=300, passes_completed=210.0)
    )

    assert METRICS["pass_completion_pct"]([sample]) == pytest.approx(75.0)


def test_penalty_conversion__is_undefined_without_penalties() -> None:
    assert math.isnan(METRICS["penalty_conversion_pct"]([make_sample()]))


def test_penalty_conversion__is_scored_over_taken() -> None:
    samples = [make_sample(penalties=1, penalties_scored=1), make_sample(penalties=1)]

    assert METRICS["penalty_conversion_pct"](samples) == 50.0


def test_possession_spread__is_the_standard_deviation_in_percentage_points() -> None:
    samples = [make_sample(make_side(possession=0.4)), make_sample(make_side(possession=0.6))]

    assert METRICS["possession_spread_pp"](samples) == pytest.approx(10.0)


def test_every_metric__is_nan_on_an_empty_sample_list() -> None:
    assert all(math.isnan(metric([])) for metric in METRICS.values())


def test_favourite_bins__the_favourite_is_the_higher_rated_side_whichever_venue() -> None:
    home_favourite_won = _scored(2, 0, gap=10.0)
    away_favourite_won = _scored(0, 2, gap=-10.0)
    upset = _scored(0, 1, gap=10.0)

    samples = [home_favourite_won, away_favourite_won, upset]

    assert METRICS["favourite_win_pct_medium"](samples) == pytest.approx(200 / 3)
    assert METRICS["underdog_win_pct_medium"](samples) == pytest.approx(100 / 3)
    assert math.isnan(METRICS["favourite_win_pct_large"](samples))


def test_home_favourite_edge__is_home_favourite_win_rate_minus_away_favourite_win_rate() -> None:
    samples = [
        _scored(1, 0, gap=5.0),
        _scored(1, 0, gap=5.0),
        _scored(0, 1, gap=-5.0),
        _scored(1, 1, gap=-5.0),
    ]

    assert METRICS["home_favourite_edge_pp"](samples) == 50.0


def test_favourite_win_rises_with_gap__needs_every_bin_strictly_higher() -> None:
    rising = [
        _scored(1, 1, gap=1.0),
        _scored(1, 0, gap=5.0),
        _scored(0, 1, gap=5.0),
        _scored(1, 0, gap=10.0),
        _scored(1, 0, gap=10.0),
        _scored(0, 1, gap=10.0),
        _scored(1, 0, gap=20.0),
        _scored(1, 0, gap=20.0),
        _scored(1, 0, gap=20.0),
    ]
    flat = [_scored(1, 0, gap=g) for g in (1.0, 5.0, 10.0, 20.0)]

    assert METRICS["favourite_win_rises_with_gap"](rising) == 1.0
    assert METRICS["favourite_win_rises_with_gap"](flat) == 0.0
