"""The first summer window of a four-club league: what the market did and what it must keep."""

from __future__ import annotations

import datetime as dt
from functools import cache

import pytest

from footystreams.domain.finance import LedgerCategory
from footystreams.domain.player import PlayerStatus
from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.persistence.ports import UnitOfWorkFactory
from footystreams.verify import SquadRules, check_ledger, check_squads
from tests.factories.league_config import make_development_config
from tests.factories.league_transfers import run_until, runner_for
from tests.factories.world import make_world
from tests.helpers.assertions import assert_no_violations

pytestmark = pytest.mark.timeout(120)
SQUAD = make_development_config().squad
RULES = SquadRules(SQUAD.min_senior, SQUAD.max_senior, SQUAD.min_goalkeepers)
CLOSE = dt.date(2031, 8, 15)  # the day after the window closes


@cache
def _summer() -> UnitOfWorkFactory:
    runner, factory = runner_for(2, 4)
    run_until(runner, CLOSE, factory)
    return factory


def test_window__clubs_make_deals_and_every_bid_is_accounted_for() -> None:
    with _summer()() as uow:
        transfers, bids = uow.transfers.all(), uow.bids.all()
    assert transfers
    assert {b.status for b in bids} <= {
        "accepted", "rejected", "player_refused", "unaffordable", "failed_medical"
    }  # fmt: skip
    assert sum(b.status == "accepted" for b in bids) == len(transfers)


def test_window__every_transfer_falls_inside_the_window() -> None:
    with _summer()() as uow:
        window = uow.windows.all()[0]
        transfers = uow.transfers.all()
    assert all(window.opens_on <= t.completed_on <= window.closes_on for t in transfers)


def test_ledger__both_legs_of_a_fee_are_equal_and_opposite() -> None:
    with _summer()() as uow:
        paid = [t for t in uow.transfers.all() if t.fee > 0]
        legs = {t.id: uow.ledger.find({"ref_type": "transfer_id", "ref_id": t.id}) for t in paid}
    assert paid
    for transfer in paid:
        amounts = sorted(e.amount for e in legs[transfer.id])
        assert amounts == [-transfer.fee, transfer.fee]
        assert {e.category for e in legs[transfer.id]} == {
            LedgerCategory.TRANSFER_FEES,
            LedgerCategory.PLAYER_SALES,
        }


def test_ledger__the_closed_system_nets_transfers_to_zero_including_the_outside_world() -> None:
    with _summer()() as uow:
        entries = uow.ledger.all()
        clubs = uow.clubs.all()
    fees = sum(
        e.amount
        for e in entries
        if e.category in {LedgerCategory.TRANSFER_FEES, LedgerCategory.PLAYER_SALES}
    )
    assert fees == 0
    assert any(c.id == OUTSIDE_WORLD for c in clubs)
    assert_no_violations(check_ledger(clubs, entries))


def test_budget__no_club_pays_more_in_fees_than_it_started_with_plus_what_it_sold() -> None:
    start = {c.id: c.finances.transfer_budget for c in make_world(2, 4).clubs}
    with _summer()() as uow:
        transfers = uow.transfers.all()
    for club_id, budget in start.items():
        spent = sum(t.fee for t in transfers if t.to_club_id == club_id)
        received = sum(t.fee for t in transfers if t.from_club_id == club_id)
        assert spent <= budget + received


def test_window_close__every_club_has_a_legal_squad() -> None:
    with _summer()() as uow:
        players = uow.players.all()
        clubs = [c.id for c in uow.clubs.all() if c.id != OUTSIDE_WORLD]
    assert_no_violations(check_squads(players, clubs, RULES))


def test_window_close__squad_entries_match_the_contracted_players_with_unique_numbers() -> None:
    with _summer()() as uow:
        entries = uow.squad_entries.all()
        players = uow.players.all()
    contracted = {
        (p.contract.club_id, p.id)
        for p in players
        if p.contract is not None
        and p.status is PlayerStatus.ACTIVE
        and p.contract.club_id != OUTSIDE_WORLD
    }
    assert {(e.club_id, e.player_id) for e in entries} == contracted
    per_club = [(e.club_id, e.squad_number) for e in entries]
    assert len(per_club) == len(set(per_club))


def test_window_close__signed_players_have_a_contract_at_their_new_club() -> None:
    with _summer()() as uow:
        transfers = uow.transfers.all()
        players = {p.id: p for p in uow.players.all()}
    for transfer in transfers:
        player = players[transfer.player_id]
        assert player.contract is not None or player.status is not PlayerStatus.ACTIVE
        if player.contract and player.contract.start == transfer.completed_on:
            assert player.contract.club_id == transfer.to_club_id


def _ratio(fee: object, value: object) -> float:
    assert isinstance(fee, int)
    assert isinstance(value, int)
    return fee / value


def test_window__the_fee_is_close_to_the_market_value() -> None:
    with _summer()() as uow:
        news = [e for e in uow.world_events.all() if e.kind == "transfer_completed"]
    ratios = [
        _ratio(e.facts["fee"], e.facts["value"])
        for e in news
        if e.facts["fee"] and e.facts["value"]
    ]
    assert ratios
    assert 0.5 < sum(ratios) / len(ratios) < 2.0


def test_window__the_outside_world_supplies_and_buys() -> None:
    with _summer()() as uow:
        transfers = uow.transfers.all()
        club = uow.clubs.get(OUTSIDE_WORLD)
    assert club is not None
    assert any(OUTSIDE_WORLD in (t.from_club_id, t.to_club_id) for t in transfers)
