"""L01-L03: each league invariant passes on a played season and fails on a canary."""

from __future__ import annotations

from typing import NamedTuple

from footystreams.domain.club import Club
from footystreams.domain.finance import LedgerCategory, LedgerEntry
from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.match import Match, MatchStatus
from footystreams.events.summary import MatchSummary
from footystreams.verify import check_ledger, check_results, check_season_complete
from tests.factories.league_run import cached_small_season
from tests.helpers.assertions import assert_no_violations


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
