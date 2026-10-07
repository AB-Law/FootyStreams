"""L01-L05: each league invariant passes on a played season and fails on a canary."""

from __future__ import annotations

import datetime as dt
from functools import cache
from typing import NamedTuple

import pytest

from footystreams.domain.club import Club
from footystreams.domain.development import DevelopmentEntry
from footystreams.domain.finance import LedgerCategory, LedgerEntry
from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.match import Match, MatchStatus
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.transfer import OUTSIDE_WORLD, Transfer
from footystreams.domain.types import ClubId, Position
from footystreams.events.summary import MatchSummary
from footystreams.verify import (
    SquadRules,
    check_development,
    check_ledger,
    check_results,
    check_season_complete,
    check_squads,
    check_transfers,
)
from tests.factories.league_run import cached_rolled_over, cached_small_season
from tests.factories.league_transfers import run_until, runner_for
from tests.helpers.assertions import assert_no_violations

pytestmark = pytest.mark.timeout(120)  # these build whole seasons; allow for a loaded machine


class _State(NamedTuple):
    clubs: list[Club]
    entries: list[LedgerEntry]
    fixtures: list[Fixture]
    matches: list[Match]
    summaries: dict[str, MatchSummary]


def _state() -> _State:
    _, factory = cached_small_season()
    with factory() as uow:
        return _State(
            uow.clubs.all(),
            uow.ledger.all(),
            uow.fixtures.all(),
            uow.matches.all(),
            {s.match_id: s.summary for s in uow.summaries.all()},
        )


def test_checks__played_season__are_clean() -> None:
    clubs, entries, fixtures, matches, summaries = _state()
    assert_no_violations(check_ledger(clubs, entries))
    assert_no_violations(check_results(fixtures, matches, summaries))
    assert_no_violations(check_season_complete(fixtures))


def test_check_ledger__balance_off_by_one__is_l01() -> None:
    clubs, entries, *_ = _state()
    moved = clubs[0].model_copy(
        update={
            "finances": clubs[0].finances.model_copy(
                update={"balance": clubs[0].finances.balance + 1}
            )
        }
    )
    assert {v.code for v in check_ledger([moved, *clubs[1:]], entries)} == {"L01"}


def test_check_ledger__duplicate_entry__is_l01() -> None:
    clubs, entries, *_ = _state()
    extra = LedgerEntry(
        id=entries[0].id, club_id=entries[0].club_id, date=entries[0].date,
        category=LedgerCategory.OTHER, amount=0,
    )  # fmt: skip
    assert any("twice" in v.message for v in check_ledger(clubs, [*entries, extra]))


def test_check_results__fixture_marked_played_without_a_match__is_l02() -> None:
    _, _, fixtures, matches, summaries = _state()
    assert any(v.code == "L02" for v in check_results(fixtures, matches[1:], summaries))


def test_check_results__scheduled_fixture_with_a_match__is_l02() -> None:
    _, _, fixtures, matches, summaries = _state()
    unplayed = [fixtures[0].model_copy(update={"status": FixtureStatus.SCHEDULED}), *fixtures[1:]]
    assert any(v.code == "L02" for v in check_results(unplayed, matches, summaries))


def test_check_results__match_problems__are_each_reported() -> None:
    _, _, fixtures, matches, summaries = _state()
    open_match = matches[0].model_copy(update={"status": MatchStatus.SCHEDULED})
    swapped = matches[1].model_copy(
        update={"home_club_id": matches[1].away_club_id, "away_club_id": matches[1].home_club_id}
    )
    wrong_score = matches[2].model_copy(update={"home_goals": (matches[2].home_goals or 0) + 1})
    broken = [open_match, swapped, wrong_score, *matches[3:]]
    messages = " ".join(v.message for v in check_results(fixtures, broken, summaries))
    assert "not completed" in messages
    assert "differ from the fixture" in messages
    assert "differs from its summary" in messages
    assert "no stored summary" in " ".join(v.message for v in check_results(fixtures, matches, {}))


def test_check_season_complete__unplayed_fixture__is_l03() -> None:
    *_, fixtures, _, _ = _state()
    open_season = [
        fixtures[0].model_copy(update={"status": FixtureStatus.SCHEDULED}),
        *fixtures[1:],
    ]
    assert {v.code for v in check_season_complete(open_season)} == {"L03"}


RULES = SquadRules(min_senior=22, max_senior=28, min_goalkeepers=2)


def _rolled_players() -> tuple[list[Player], list[ClubId]]:
    _, factory = cached_rolled_over()
    with factory() as uow:
        league = [club.id for club in uow.clubs.all() if club.id != OUTSIDE_WORLD]
        return uow.players.all(), league


def test_check_squads_and_development__after_a_rollover__are_clean() -> None:
    players, clubs = _rolled_players()
    assert_no_violations(check_squads(players, clubs, RULES))
    assert_no_violations(check_development(players))


def test_check_squads__too_few_seniors_or_keepers__is_l04() -> None:
    players, clubs = _rolled_players()
    first = clubs[0]
    keepers_gone = [
        p for p in players
        if not (p.contract and p.contract.club_id == first and p.primary_position is Position.GK)
    ]  # fmt: skip
    messages = " ".join(v.message for v in check_squads(keepers_gone, clubs, RULES))
    assert "goalkeepers" in messages
    short = [p for p in players if not (p.contract and p.contract.club_id == first)]
    assert any("senior players" in v.message for v in check_squads(short, clubs, RULES))
    assert {v.code for v in check_squads(short, clubs, RULES)} == {"L04"}


def test_check_development__broken_players__are_l05() -> None:
    players, _ = _rolled_players()
    over = players[0].model_copy(update={"ability_current": 99, "ability_potential": 50})
    entry = DevelopmentEntry(date=dt.date(2032, 1, 1), attr="pace", delta=1, cause="training")
    long_log = players[1].model_copy(update={"development_log": (entry,) * 25})
    ghost = next(p for p in players if p.contract).model_copy(
        update={"status": PlayerStatus.RETIRED}
    )
    messages = " ".join(v.message for v in check_development([over, long_log, ghost]))
    assert "exceeds potential" in messages
    assert "development log has" in messages
    assert "retired player still has a contract" in messages


@cache
def _market_state() -> tuple[list[Transfer], list[LedgerEntry]]:
    runner, factory = runner_for(2, 4)
    run_until(runner, dt.date(2031, 8, 15), factory)
    with factory() as uow:
        return uow.transfers.all(), uow.ledger.all()


def test_check_transfers__a_played_window_is_clean() -> None:
    transfers, entries = _market_state()
    assert any(t.fee > 0 for t in transfers)
    assert_no_violations(check_transfers(transfers, entries))


def test_check_transfers__missing_wrong_or_stray_legs_are_l06() -> None:
    transfers, entries = _market_state()
    paid = next(t for t in transfers if t.fee > 0)
    without = [e for e in entries if e.ref.get("transfer_id") != paid.id]
    assert {v.code for v in check_transfers(transfers, without)} == {"L06"}
    one_leg = [e for e in entries if not (e.ref.get("transfer_id") == paid.id and e.amount > 0)]
    assert any("seller's leg" in v.message for v in check_transfers(transfers, one_leg))
    free = paid.model_copy(update={"fee": 0})
    assert any("free transfer" in v.message for v in check_transfers([free], entries))
