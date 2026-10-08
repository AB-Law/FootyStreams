from __future__ import annotations

import datetime as dt

import pytest

from footystreams.domain.mood import ModifierVisibility, StateKind
from footystreams.domain.rng import WorldRng
from footystreams.domain.standings import StandingRow
from footystreams.domain.types import PlayerId
from footystreams.league.awards import (
    SeasonTotals,
    award_modifiers,
    best_player,
    season_awards,
    season_totals,
    top_scorer,
)
from footystreams.league.club_year import (
    expected_places,
    performance,
    renew_sponsors,
    reset_budgets,
    update_standing,
)
from footystreams.league.finance import income_estimate
from tests.factories.league_config import (
    make_development_config,
    make_league_config,
    make_mood_config,
)
from tests.factories.league_run import cached_small_season
from tests.factories.world import make_world

pytestmark = pytest.mark.timeout(120)  # these build whole seasons; allow for a loaded machine

ROLLOVER = make_development_config().rollover
FINANCE = make_league_config().finance
WORLD = make_world(1)
TODAY = dt.date(2032, 6, 1)


def test_season_totals__folds_every_summary_into_per_player_totals() -> None:
    _, factory = cached_small_season()
    with factory() as uow:
        summaries = [r.summary for r in uow.summaries.all()]
    totals = season_totals(summaries)
    assert sum(t.goals for t in totals.values()) == sum(
        s.score_home + s.score_away for s in summaries
    )
    assert sum(t.appearances for t in totals.values()) == 22 * len(summaries)
    assert all(t.minutes <= 90 * t.appearances for t in totals.values())


def test_top_scorer_and_best_player__follow_the_totals_with_stable_tiebreaks() -> None:
    totals = {
        PlayerId("plr_aaaa"): SeasonTotals(appearances=10, minutes=900, goals=5, rating_sum=70.0),
        PlayerId("plr_bbbb"): SeasonTotals(appearances=10, minutes=800, goals=5, rating_sum=75.0),
        PlayerId("plr_cccc"): SeasonTotals(appearances=2, minutes=180, goals=1, rating_sum=19.0),
    }
    assert top_scorer(totals) == "plr_bbbb"
    assert best_player(totals, 6) == "plr_bbbb"
    assert best_player(totals, 20) is None
    assert top_scorer({PlayerId("plr_aaaa"): SeasonTotals()}) is None


def test_season_awards__champion_first_then_the_individual_awards() -> None:
    table = [StandingRow(season_id="ssn_00001", club_id="clb_00003", points=30, position=1)]  # type: ignore[arg-type]
    totals = {
        PlayerId("plr_aaaa"): SeasonTotals(appearances=10, minutes=900, goals=7, rating_sum=72.0)
    }
    events = season_awards(table, totals, ("2031/32", TODAY, 6))
    assert [e.kind for e in events] == ["league_champion", "top_scorer", "player_of_the_season"]
    assert all(e.visibility is ModifierVisibility.PUBLIC for e in events)
    assert season_awards(table, {}, ("2031/32", TODAY, 6))[0].kind == "league_champion"


def test_award_modifiers__one_per_winner_in_a_stable_order() -> None:
    winners = {
        StateKind.TROPHY_GLOW: [PlayerId("plr_bbbb"), PlayerId("plr_aaaa")],
        StateKind.AWARD_GLOW: [PlayerId("plr_aaaa")],
    }
    mods = award_modifiers(winners, TODAY, make_mood_config())
    assert [(m.kind, m.owner.id) for m in mods] == [
        (StateKind.AWARD_GLOW, "plr_aaaa"),
        (StateKind.TROPHY_GLOW, "plr_aaaa"),
        (StateKind.TROPHY_GLOW, "plr_bbbb"),
    ]


def test_expected_places__by_reputation_best_first() -> None:
    places = expected_places(WORLD.clubs)
    best = max(WORLD.clubs, key=lambda c: (c.club_reputation, -int(c.id[-1], 36)))
    assert places[best.id] == 1
    assert sorted(places.values()) == list(range(1, len(WORLD.clubs) + 1))


def test_performance__positive_above_expectation() -> None:
    assert performance(5, 1, 8) > 0 > performance(1, 5, 8)
    assert performance(3, 3, 8) == 0
    assert performance(1, 1, 1) == 0


def test_update_standing__a_good_year_lifts_reputation_support_and_confidence() -> None:
    club = WORLD.clubs[3]
    up = update_standing(club, 1.0, 8, ROLLOVER)
    down = update_standing(club, -1.0, 8, ROLLOVER)
    assert up.club_reputation > club.club_reputation > down.club_reputation
    assert up.fanbase.size > club.fanbase.size > down.fanbase.size
    assert (
        up.board.manager_confidence
        >= club.board.manager_confidence
        >= down.board.manager_confidence
    )
    assert up.club_reputation - club.club_reputation <= ROLLOVER.reputation_max_change


def test_update_standing__reputation_stays_in_range() -> None:
    top = WORLD.clubs[0].model_copy(update={"club_reputation": 100})
    assert update_standing(top, 1.0, 8, ROLLOVER).club_reputation == 100


def test_renew_sponsors__only_expired_deals_are_renewed_and_reputation_moves_the_value() -> None:
    club = WORLD.clubs[0]
    late = dt.date(2099, 1, 1)
    renewed = renew_sponsors(club, late, 3, (ROLLOVER, WorldRng(1)))
    assert all(d.ends_on > late for d in renewed)
    assert all(
        new.annual_value > old.annual_value
        for new, old in zip(renewed, club.finances.sponsor_deals, strict=True)
    )


def test_renew_sponsors__live_deals_are_kept_as_they_are() -> None:
    club = WORLD.clubs[0]
    long_deals = tuple(
        d.model_copy(update={"ends_on": dt.date(2090, 6, 30)}) for d in club.finances.sponsor_deals
    )
    live = club.model_copy(
        update={"finances": club.finances.model_copy(update={"sponsor_deals": long_deals})}
    )
    assert renew_sponsors(live, TODAY, 5, (ROLLOVER, WorldRng(1))) == long_deals


def test_income_estimate__grows_with_a_bigger_ground_and_more_sponsors() -> None:
    club = WORLD.clubs[0]
    bigger = club.model_copy(
        update={"stadium": club.stadium.model_copy(update={"capacity": club.stadium.capacity * 2})}
    )
    assert income_estimate(bigger, FINANCE) > income_estimate(club, FINANCE) > 0


def test_reset_budgets__wage_budget_follows_income_and_transfer_budget_the_bank() -> None:
    club = WORLD.clubs[0].model_copy(
        update={"finances": WORLD.clubs[0].finances.model_copy(update={"balance": 10_000_000})}
    )
    reset = reset_budgets(club, FINANCE, ROLLOVER)
    expected = round(
        income_estimate(club, FINANCE) * ROLLOVER.wage_budget_ratio / FINANCE.weeks_per_year
    )
    assert reset.finances.wage_budget_weekly == expected
    assert reset.finances.transfer_budget == round(10_000_000 * ROLLOVER.transfer_budget_share)
    broke = club.model_copy(update={"finances": club.finances.model_copy(update={"balance": -5})})
    assert reset_budgets(broke, FINANCE, ROLLOVER).finances.transfer_budget == 0
