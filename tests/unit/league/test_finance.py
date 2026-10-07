from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from footystreams.domain.finance import LedgerCategory
from footystreams.league.finance import (
    apportion,
    gate_income,
    is_pay_day,
    matchday_postings,
    season_end_postings,
    wage_bills,
    weekly_postings,
)
from footystreams.league.ledger import Posting, book
from footystreams.league.outcome import Outcome, outcome_for
from tests.factories.league_config import make_league_config
from tests.factories.league_inputs import make_team_inputs
from tests.factories.world import make_world

CONFIG = make_league_config().finance
WORLD = make_world(1)
CLUB = WORLD.clubs[0]
TEAM = make_team_inputs(WORLD, 0)
MONDAY = dt.date(2031, 8, 18)


def _amount(postings: list[Posting], memo: str) -> int:
    return next(p.amount for p in postings if p.memo_key == memo)


def test_outcome_for__scores__maps_to_win_draw_loss() -> None:
    assert outcome_for(2, 1) is Outcome.WIN
    assert outcome_for(1, 1) is Outcome.DRAW
    assert outcome_for(0, 3) is Outcome.LOSS


def test_is_pay_day__only_on_the_configured_weekday() -> None:
    assert is_pay_day(MONDAY, CONFIG)
    assert not is_pay_day(MONDAY + dt.timedelta(days=1), CONFIG)


def test_wage_bills__sums_players_staff_and_manager() -> None:
    bills = wage_bills(TEAM.squad, TEAM.staff, TEAM.manager)
    assert bills.players == sum(p.contract.wage_weekly for p in TEAM.squad if p.contract)
    manager_wage = TEAM.manager.contract.wage_weekly if TEAM.manager.contract else 0
    assert (
        bills.staff == sum(s.contract.wage_weekly for s in TEAM.staff if s.contract) + manager_wage
    )


def test_wage_bills__no_manager__counts_staff_only() -> None:
    assert wage_bills([], TEAM.staff, None).staff == sum(
        s.contract.wage_weekly for s in TEAM.staff if s.contract
    )


def test_gate_income__scales_with_attendance_and_price() -> None:
    gate, hospitality = gate_income(10_000, CLUB, CONFIG)
    assert gate == round(10_000 * CLUB.stadium.ticket_price_base * CONFIG.ticket_price_scale)
    assert hospitality == round(gate * CONFIG.hospitality_share_of_gate)
    assert gate_income(20_000, CLUB, CONFIG)[0] > gate


def test_matchday_postings__a_win_sells_more_merchandise_than_a_loss() -> None:
    win = matchday_postings(CLUB, ("mch_1", 30_000, Outcome.WIN), MONDAY, CONFIG)
    loss = matchday_postings(CLUB, ("mch_1", 30_000, Outcome.LOSS), MONDAY, CONFIG)
    assert _amount(win, "matchday_merchandise") > _amount(loss, "matchday_merchandise")
    assert {p.category for p in win} == {LedgerCategory.MATCHDAY, LedgerCategory.MERCHANDISE}
    assert all(p.ref == {"match_id": "mch_1"} for p in win)


def test_weekly_postings__income_and_costs_have_the_right_signs() -> None:
    bills = wage_bills(TEAM.squad, TEAM.staff, TEAM.manager)
    postings = weekly_postings(CLUB, bills, MONDAY, CONFIG)
    income = {"sponsor_instalment", "broadcast_instalment", "weekly_merchandise"}
    assert all(p.amount >= 0 for p in postings if p.memo_key in income)
    assert all(p.amount <= 0 for p in postings if p.memo_key not in income)
    assert _amount(postings, "player_wages") == -bills.players


def test_weekly_postings__expired_sponsor_deal__pays_nothing() -> None:
    late = dt.date(2099, 1, 1)
    postings = weekly_postings(CLUB, wage_bills([], [], None), late, CONFIG)
    assert _amount(postings, "sponsor_instalment") == 0


def test_weekly_postings__debt__costs_weekly_interest() -> None:
    indebted = CLUB.model_copy(
        update={
            "finances": CLUB.finances.model_copy(
                update={"debt": 52_000_000, "debt_interest_rate": 0.05}
            )
        }
    )
    postings = weekly_postings(indebted, wage_bills([], [], None), MONDAY, CONFIG)
    assert _amount(postings, "debt_interest") == -50_000


@given(
    total=st.integers(0, 10**9),
    weights=st.lists(st.floats(0.01, 10.0), min_size=1, max_size=20),
)
def test_apportion__always_splits_the_total_exactly(total: int, weights: list[float]) -> None:
    shares = apportion(total, weights)
    assert sum(shares) == total
    assert all(share >= 0 for share in shares)


def test_apportion__higher_weight__never_gets_less() -> None:
    shares = apportion(1_000_003, [1.0, 0.78, 0.61, 0.47])
    assert shares == sorted(shares, reverse=True)


def test_season_end_postings__pay_the_whole_pool_and_favour_the_top() -> None:
    table = [c.id for c in WORLD.clubs]
    postings = season_end_postings(table, WORLD.clubs, MONDAY, CONFIG)
    prizes = [p.amount for p in postings if p.memo_key == "league_prize"]
    broadcast = sum(c.finances.broadcast_share for c in WORLD.clubs)
    assert sum(prizes) == round(broadcast * CONFIG.prize_pool_share_of_broadcast)
    assert prizes == sorted(prizes, reverse=True)
    merit = sum(p.amount for p in postings if p.memo_key == "broadcast_merit")
    assert merit == round(broadcast * CONFIG.broadcast_merit_share)


def test_book__moves_each_balance_by_exactly_the_entries_sum() -> None:
    clubs = {c.id: c for c in WORLD.clubs}
    bills = wage_bills(TEAM.squad, TEAM.staff, TEAM.manager)
    postings = weekly_postings(CLUB, bills, MONDAY, CONFIG)
    delta = book(clubs, postings)
    (updated,) = delta.clubs
    assert updated.finances.balance == CLUB.finances.balance + sum(e.amount for e in delta.ledger)
    assert updated.finances.last_reconciled_on == MONDAY
    assert all(e.amount != 0 for e in delta.ledger)


def test_book__same_postings_twice__same_entry_ids() -> None:
    clubs = {c.id: c for c in WORLD.clubs}
    postings = matchday_postings(CLUB, ("mch_1", 20_000, Outcome.DRAW), MONDAY, CONFIG)
    first, second = book(clubs, postings), book(clubs, postings)
    assert first.content_hash() == second.content_hash()
    assert len({e.id for e in first.ledger}) == len(first.ledger)


def test_book__zero_amount_posting__writes_nothing() -> None:
    clubs = {c.id: c for c in WORLD.clubs}
    zero = Posting(CLUB.id, MONDAY, LedgerCategory.OTHER, 0, "nothing")
    assert book(clubs, [zero]).is_empty()
