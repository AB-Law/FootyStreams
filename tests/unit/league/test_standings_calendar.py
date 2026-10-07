from __future__ import annotations

import datetime as dt

import pytest

from footystreams.domain.mood import StateKind
from footystreams.domain.standings import MatchScore
from footystreams.domain.transfer import WindowKind
from footystreams.domain.types import ClubId, SeasonId
from footystreams.league.calendar import contract_end_after, matchday_dates, window_dates
from footystreams.league.standings import compute_table, table_order
from tests.factories.league_config import make_league_config, make_mood_config

X, Y, Z, W = (ClubId(f"clb_0000{i}") for i in range(1, 5))
SEASON = SeasonId("ssn_00001")


def _score(home: ClubId, away: ClubId, home_goals: int, away_goals: int) -> MatchScore:
    return MatchScore(
        home_club_id=home, away_club_id=away, home_goals=home_goals, away_goals=away_goals
    )


def test_table_order__points_then_goal_difference_then_goals_scored() -> None:
    results = [_score(X, Y, 3, 0), _score(Z, W, 1, 0), _score(X, Z, 0, 0), _score(Y, W, 2, 2)]
    # X 4pts GD+3 | Z 4pts GD+1 | Y 1pt GD-3 GF2 | W 1pt GD-3 GF2: Y/W tie goes to head to head
    assert table_order([X, Y, Z, W], results)[:2] == [X, Z]


def test_table_order__goals_scored_breaks_a_points_and_difference_tie() -> None:
    results = [_score(X, Y, 1, 1), _score(Z, W, 3, 3)]
    assert table_order([X, Y, Z, W], results) == [Z, W, X, Y]


def test_table_order__head_to_head_breaks_a_tie_on_points_difference_and_goals() -> None:
    # X, Y, Z: 3 points, goal difference 0 each; goals for X1, Y2, Z2. Y and Z are level on
    # everything until head-to-head, which Y won 2-1.
    results = [_score(X, Y, 1, 0), _score(Y, Z, 2, 1), _score(Z, X, 1, 0)]
    assert table_order([X, Y, Z], results) == [Y, Z, X]


def test_table_order__completely_level_clubs_fall_back_to_club_id() -> None:
    results = [_score(X, Y, 0, 0), _score(Y, Z, 0, 0), _score(Z, X, 0, 0)]
    assert table_order([Z, Y, X], results) == [X, Y, Z]


def test_table_order__clubs_without_matches_still_appear() -> None:
    assert table_order([Z, X], []) == [X, Z]


def test_compute_table__counts_and_positions() -> None:
    table = compute_table(SEASON, [X, Y], [_score(X, Y, 2, 1), _score(Y, X, 0, 0)])
    first, second = table
    assert (first.club_id, first.position, first.points, first.won, first.drawn) == (X, 1, 4, 1, 1)
    assert (second.club_id, second.lost, second.goals_against, second.goal_difference) == (
        Y,
        1,
        2,
        -1,
    )
    assert sum(r.goals_for for r in table) == sum(r.goals_against for r in table)


def test_matchday_dates__evenly_spaced_from_the_start() -> None:
    calendar = make_league_config().calendar
    dates = matchday_dates(calendar, dt.date(2031, 8, 15), 14)
    assert dates[0] == dt.date(2031, 8, 15)
    assert (dates[1] - dates[0]).days == calendar.matchday_spacing_days
    assert dates[-1] < calendar.season_end_in(2031)


def test_window_dates__midseason_follows_matchday_seven_and_summer_ends_before_the_season() -> None:
    calendar = make_league_config().calendar
    start = calendar.season_start_in(2031)
    dates = matchday_dates(calendar, start, 14)
    opens, closes = window_dates(calendar, WindowKind.MIDSEASON, start, dates)
    assert opens == dates[6] + dt.timedelta(days=1)
    assert (closes - opens).days == calendar.midseason_window_days - 1
    summer_open, summer_close = window_dates(calendar, WindowKind.SUMMER, start, dates)
    assert summer_open > calendar.season_end_in(2031)
    assert summer_close < calendar.season_start_in(2032)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (dt.date(2031, 7, 1), dt.date(2032, 6, 30)),
        (dt.date(2032, 6, 29), dt.date(2032, 6, 30)),
        (dt.date(2032, 6, 30), dt.date(2033, 6, 30)),
    ],
)
def test_contract_end_after__is_the_next_june_30(today: dt.date, expected: dt.date) -> None:
    assert contract_end_after(make_league_config().calendar, today) == expected


def test_mood_config__covers_every_state_kind_and_decays_are_well_formed() -> None:
    kinds = make_mood_config().kinds
    assert set(kinds) == {kind.value for kind in StateKind}
    for name, effect in kinds.items():
        if effect.decay == "half_life":
            assert effect.half_life_days, name
