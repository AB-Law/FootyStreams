import pytest

from footystreams.domain.types import PlayerId
from footystreams.events.derive.ratings import player_of_the_match, rate_match, rate_player
from footystreams.events.summary import PlayerMatchStats
from tests.helpers.logs import context_result


def _row(player_id: str = "plr_home0009", **stats: object) -> PlayerMatchStats:
    defaults: dict[str, object] = {"position": "ST", "minutes": 90}
    return PlayerMatchStats(player_id=player_id, **{**defaults, **stats})  # type: ignore[arg-type]


def test_rate_player__a_quiet_draw_is_a_six() -> None:
    assert rate_player(_row(), 0).rating == 6.0


def test_rate_player__goals_assists_and_a_win_lift_the_rating() -> None:
    star = rate_player(_row(goals=2, assists=1, xg=1.0), 1)
    assert star.rating > 8.5
    assert star.breakdown["goals"] == pytest.approx(1.8)
    assert star.breakdown["result"] == 0.25


def test_rate_player__goals_are_worth_less_to_a_defender_than_a_striker() -> None:
    forward = rate_player(_row(goals=1), 0).rating
    defender = rate_player(_row(position="CB", goals=1), 0).rating
    assert defender < forward


def test_rate_player__cards_and_defeat_pull_it_down_and_the_floor_holds() -> None:
    assert rate_player(_row(yellows=1), -1).rating == 5.5
    assert rate_player(_row(reds=1, yellows=1), -1).rating == 4.5
    heap = rate_player(_row(position="GK", goals_conceded=40, reds=3), -1)
    assert heap.rating == 3.0


def test_rate_player__the_ceiling_holds() -> None:
    assert rate_player(_row(goals=9, assists=9), 1).rating == 10.0


def test_rate_player__a_keeper_is_paid_for_saves_and_clean_sheets() -> None:
    keeper = rate_player(_row(position="GK", saves=6, clean_sheet=True), 1)
    conceding = rate_player(_row(position="GK", saves=6, goals_conceded=3), -1)
    assert keeper.rating >= 7.5
    assert conceding.rating < keeper.rating


def test_rate_player__passing_above_par_counts_only_with_enough_passes() -> None:
    few = rate_player(_row(position="CM", passes=10, passes_completed=10), 0)
    many = rate_player(_row(position="CM", passes=60, passes_completed=57), 0)
    assert few.rating == 6.0
    assert many.rating > 6.0


def test_rate_player__a_cameo_regresses_toward_six() -> None:
    full = rate_player(_row(goals=1, minutes=90), 0).rating
    cameo = rate_player(_row(goals=1, minutes=10), 0).rating
    assert 6.0 < cameo < full


def test_rate_match__the_result_cuts_both_ways() -> None:
    rows = [_row("plr_home0009"), _row("plr_away0009")]
    sides = {PlayerId("plr_home0009"): "home", PlayerId("plr_away0009"): "away"}
    home, away = rate_match(rows, sides, 2)
    assert home.rating > away.rating


def test_player_of_the_match__best_rating_then_goal_involvement() -> None:
    rows = [_row("plr_home0009", goals=1), _row("plr_home0010", assists=1, xg=0.0)]
    sides = {row.player_id: "home" for row in rows}
    ratings = rate_match(rows, sides, 0)
    assert player_of_the_match(rows, ratings) == "plr_home0009"
    assert player_of_the_match([], []) is None


def test_real_match__every_player_is_rated_between_three_and_ten_and_there_is_a_best() -> None:
    summary = context_result().summary
    assert len(summary.ratings) == len(summary.player_stats)
    assert all(3.0 <= rating.rating <= 10.0 for rating in summary.ratings)
    assert [row.rating for row in summary.player_stats] == [r.rating for r in summary.ratings]
    best = max(rating.rating for rating in summary.ratings)
    potm = next(r for r in summary.ratings if r.player_id == summary.player_of_the_match)
    assert potm.rating == best
