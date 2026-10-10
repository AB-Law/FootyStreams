"""The season, the table and the form: pure arithmetic over club ids and results."""

from __future__ import annotations

import datetime as dt
from collections import Counter

from footystreams.extensions.show.bible import Result, Scorer
from footystreams.extensions.show.ledger import (
    biggest_win,
    form,
    meetings,
    position,
    scoreline,
    table,
    top_scorers,
)
from footystreams.extensions.show.schedule import (
    fixture_key,
    match_seed,
    season_fixtures,
    show_date,
)

CLUBS = [f"clb_{n:05d}" for n in range(1, 9)]
NAMES = {club: f"Club {n}" for n, club in enumerate(CLUBS, start=1)}


def result(home: str, away: str, home_goals: int, away_goals: int, matchday: int = 1) -> Result:
    return Result(
        fixture_key=f"s1-{home}-{away}",
        season=1,
        matchday=matchday,
        date="2031-07-01",
        home_id=home,
        away_id=away,
        home_name=NAMES[home],
        away_name=NAMES[away],
        home_goals=home_goals,
        away_goals=away_goals,
    )


def test_season_fixtures__every_club_meets_every_other_home_and_away() -> None:
    fixtures = season_fixtures(CLUBS)
    pairs = Counter((fixture.home_id, fixture.away_id) for fixture in fixtures)
    assert len(fixtures) == 8 * 7
    assert set(pairs.values()) == {1}
    assert all((away, home) in pairs for home, away in pairs)


def test_season_fixtures__no_club_plays_twice_on_a_matchday() -> None:
    fixtures = season_fixtures(CLUBS)
    for matchday in {fixture.matchday for fixture in fixtures}:
        playing = [
            club for f in fixtures if f.matchday == matchday for club in (f.home_id, f.away_id)
        ]
        assert len(playing) == len(set(playing)) == 8


def test_season_fixtures__an_odd_number_of_clubs_gets_byes() -> None:
    fixtures = season_fixtures(CLUBS[:5])
    assert len(fixtures) == 5 * 4
    assert {club for f in fixtures for club in (f.home_id, f.away_id)} == set(CLUBS[:5])


def test_season_fixtures__order_does_not_depend_on_input_order() -> None:
    assert season_fixtures(CLUBS) == season_fixtures(list(reversed(CLUBS)))


def test_match_seed__is_stable_and_differs_by_fixture() -> None:
    assert match_seed(7, 1, 3) == match_seed(7, 1, 3)
    assert len({match_seed(7, 1, index) for index in range(56)}) == 56


def test_show_date__moves_on_a_week_per_matchday_and_a_year_per_season() -> None:
    start = dt.date(2031, 7, 1)
    assert show_date(start, 1, 1) == start
    assert show_date(start, 1, 3) == start + dt.timedelta(days=14)
    assert show_date(start, 2, 1) == start + dt.timedelta(days=365)


def test_fixture_key__is_zero_padded() -> None:
    assert fixture_key(2, 5) == "s2-f005"


def test_table__orders_by_points_then_goal_difference() -> None:
    results = [
        result(CLUBS[0], CLUBS[1], 3, 0),
        result(CLUBS[2], CLUBS[3], 1, 0),
        result(CLUBS[1], CLUBS[2], 2, 2),
    ]
    rows = table(results, NAMES)
    assert [row.club_id for row in rows[:3]] == [CLUBS[2], CLUBS[0], CLUBS[1]]
    assert rows[0].points == 4
    assert rows[1].goal_difference == 3
    assert position(rows, CLUBS[0]) == 2
    assert rows[-1].club_id == CLUBS[3]
    assert len(rows) == 8


def test_table__counts_draws_and_losses() -> None:
    rows = {
        row.club_id: row
        for row in table(
            [result(CLUBS[0], CLUBS[1], 1, 1), result(CLUBS[1], CLUBS[2], 0, 2)], NAMES
        )
    }
    assert (rows[CLUBS[1]].won, rows[CLUBS[1]].drawn, rows[CLUBS[1]].lost) == (0, 1, 1)
    assert rows[CLUBS[1]].points == 1
    assert rows[CLUBS[1]].goals_against == 3


def test_form__is_the_last_five_oldest_first() -> None:
    games = [result(CLUBS[0], CLUBS[1], 1, 0), result(CLUBS[1], CLUBS[0], 2, 0)] + [
        result(CLUBS[0], CLUBS[2], 1, 1) for _ in range(4)
    ]
    assert form(games, CLUBS[0]) == "LDDDD"


def test_meetings__only_the_two_clubs_and_the_latest_few() -> None:
    games = [result(CLUBS[0], CLUBS[1], n, 0) for n in range(6)] + [
        result(CLUBS[0], CLUBS[2], 9, 9)
    ]
    found = meetings(games, CLUBS[1], CLUBS[0])
    assert [game.home_goals for game in found] == [2, 3, 4, 5]


def test_scoreline__reads_home_first() -> None:
    assert scoreline(result(CLUBS[0], CLUBS[1], 2, 1)) == "Club 1 2-1 Club 2"


def test_top_scorers__adds_goals_across_matches() -> None:
    scorer = Scorer(player_id="plr_00001", name="Ann", goals=2)
    other = Scorer(player_id="plr_00002", name="Bob", goals=1)
    a = result(CLUBS[0], CLUBS[1], 3, 0).model_copy(update={"scorers": (scorer, other)})
    b = result(CLUBS[0], CLUBS[2], 1, 0).model_copy(update={"scorers": (scorer,)})
    assert top_scorers([a, b]) == [("Ann", 4), ("Bob", 1)]


def test_biggest_win__picks_the_widest_margin() -> None:
    games = [
        result(CLUBS[0], CLUBS[1], 1, 0),
        result(CLUBS[2], CLUBS[3], 0, 4),
        result(CLUBS[4], CLUBS[5], 3, 0),
    ]
    win = biggest_win(games)
    assert win is not None
    assert win.away_goals == 4
    assert biggest_win([]) is None
