"""Repository contract: the same behaviour from the in-memory and the SQLite implementation."""

from __future__ import annotations

import datetime as dt

import pytest

from footystreams.domain.finance import LedgerCategory, LedgerEntry
from footystreams.domain.types import ClubId, Id
from footystreams.persistence.errors import ConflictError, NotFoundError
from footystreams.persistence.reader import RepositoryWorldReader
from footystreams.persistence.records import MetaEntry, StageLogEntry, StoredEvent, SummaryRecord
from footystreams.persistence.world_store import load_world, save_world
from tests.contract.conftest import UowFactory
from tests.factories.league import make_fixture, make_match
from tests.factories.result import make_match_result
from tests.factories.world import make_world

WORLD = make_world(1)


# ---------------------------------------------------------------- reading
def test_load_world__returns_exactly_the_saved_world(loaded: UowFactory) -> None:
    with loaded() as uow:
        assert load_world(uow) == WORLD


def test_get__existing_and_missing(loaded: UowFactory) -> None:
    club = WORLD.clubs[0]
    with loaded() as uow:
        assert uow.clubs.get(str(club.id)) == club
        assert uow.clubs.get("clb_missing") is None


def test_require__missing__raises_not_found_with_table_and_key(loaded: UowFactory) -> None:
    with loaded() as uow, pytest.raises(NotFoundError, match="clb_missing"):
        uow.clubs.require("clb_missing")


def test_find__by_club_matches_the_squad_of_the_club(loaded: UowFactory) -> None:
    club = WORLD.clubs[0]
    expected = [p for p in WORLD.players if p.contract and p.contract.club_id == club.id]
    with loaded() as uow:
        assert uow.players.find({"club_id": str(club.id)}) == expected


def test_find__null_criteria_matches_players_without_a_club(loaded: UowFactory) -> None:
    expected = [p for p in WORLD.players if p.contract is None]
    with loaded() as uow:
        assert uow.players.find({"club_id": None}) == expected


def test_find__several_criteria_are_anded(loaded: UowFactory) -> None:
    club = str(WORLD.clubs[0].id)
    expected = [
        p for p in WORLD.players
        if p.contract and str(p.contract.club_id) == club and p.primary_position.value == "GK"
    ]  # fmt: skip
    with loaded() as uow:
        assert uow.players.find({"club_id": club, "primary_position": "GK"}) == expected


def test_find__order_by_a_column_sorts_ascending_with_key_as_tiebreak(loaded: UowFactory) -> None:
    with loaded() as uow:
        found = uow.players.find({"club_id": str(WORLD.clubs[0].id)}, order_by="market_value")
    values = [p.market_value for p in found]
    assert values == sorted(values)


def test_find__date_and_boolean_columns(loaded: UowFactory) -> None:
    injured = [p for p in WORLD.players if p.current_injury is not None]
    with loaded() as uow:
        assert uow.players.find({"injured": True}) == injured
        assert uow.players.count({"injured": False}) == len(WORLD.players) - len(injured)
        oldest = min(p.date_of_birth for p in WORLD.players)
        assert uow.players.count({"date_of_birth": oldest}) >= 1


def test_find__unknown_column__raises_key_error(loaded: UowFactory) -> None:
    with loaded() as uow, pytest.raises(KeyError, match="no_such_column"):
        uow.players.find({"no_such_column": 1})


def test_count_and_total__match_the_data(loaded: UowFactory) -> None:
    club = str(WORLD.clubs[0].id)
    wages = sum(
        p.contract.wage_weekly
        for p in WORLD.players
        if p.contract and str(p.contract.club_id) == club
    )
    with loaded() as uow:
        assert uow.players.count() == len(WORLD.players)
        assert uow.players.total("wage_weekly", {"club_id": club}) == wages
        assert uow.players.total("wage_weekly", {"club_id": "clb_nobody"}) == 0


def test_all__is_ordered_by_key(loaded: UowFactory) -> None:
    with loaded() as uow:
        ids = [str(p.id) for p in uow.players.all()]
    assert ids == sorted(ids)


def test_ledger_total__equals_the_clubs_opening_balance(loaded: UowFactory) -> None:
    with loaded() as uow:
        for club in WORLD.clubs:
            assert uow.ledger.total("amount", {"club_id": str(club.id)}) == club.finances.balance


def test_world_reader__answers_from_any_backend(loaded: UowFactory) -> None:
    club = WORLD.clubs[0]
    with loaded() as uow:
        reader = RepositoryWorldReader(uow)
        assert reader.current_date() == WORLD.created_in_world
        assert reader.club(str(club.id)) == club
        assert len(reader.clubs()) == len(WORLD.clubs)
        assert len(reader.squad(str(club.id))) == 33
        assert reader.manager_of(str(club.id)) is not None
        assert len(reader.staff_of(str(club.id))) == 9
        assert len(reader.referees()) == 10
        assert len(reader.free_agents()) == 30
        assert reader.ledger_balance(str(club.id)) == club.finances.balance
        assert reader.fixtures(str(WORLD.seasons[0].id)) == []
        assert reader.player(str(WORLD.players[0].id)) == WORLD.players[0]


# ---------------------------------------------------------------- writing (rolled back)
def test_save__first_write_is_rev_one_and_each_update_bumps_it(loaded: UowFactory) -> None:
    club = WORLD.clubs[0]
    with loaded() as uow:
        assert uow.clubs.get_versioned(str(club.id)).rev == 1  # type: ignore[union-attr]
        renamed = club.model_copy(update={"nickname": "the Renamed"})
        assert uow.clubs.save(renamed) == 2
        saved = uow.clubs.get_versioned(str(club.id))
        assert saved is not None
        assert (saved.entity.nickname, saved.rev) == ("the Renamed", 2)


def test_save__stale_expected_rev__raises_conflict(loaded: UowFactory) -> None:
    club = WORLD.clubs[0]
    with loaded() as uow:
        uow.clubs.save(club, expected_rev=1)
        with pytest.raises(ConflictError, match="expected rev 1, found rev 2"):
            uow.clubs.save(club, expected_rev=1)


def test_save__expected_rev_on_a_missing_row__raises_conflict(loaded: UowFactory) -> None:
    club = WORLD.clubs[0].model_copy(update={"id": ClubId("clb_zzzz9"), "short_code": "ZZZ"})
    with loaded() as uow, pytest.raises(ConflictError, match="missing"):
        uow.clubs.save(club, expected_rev=1)


def test_save__duplicate_unique_column__raises_conflict(loaded: UowFactory) -> None:
    first, second = WORLD.clubs[0], WORLD.clubs[1]
    clash = second.model_copy(update={"short_code": first.short_code})
    with loaded() as uow, pytest.raises(ConflictError):
        uow.clubs.save(clash)


def test_save__duplicate_shirt_number_in_a_club__raises_conflict(loaded: UowFactory) -> None:
    entries = [e for e in WORLD.squad_entries if e.club_id == WORLD.clubs[0].id]
    clash = entries[1].model_copy(update={"squad_number": entries[0].squad_number})
    with loaded() as uow, pytest.raises(ConflictError):
        uow.squad_entries.save(clash)


def test_delete__removes_the_row_and_missing_rows_raise(loaded: UowFactory) -> None:
    spare = WORLD.referees[0]
    with loaded() as uow:
        uow.referees.delete(str(spare.id))
        assert uow.referees.get(str(spare.id)) is None
        with pytest.raises(NotFoundError):
            uow.referees.delete(str(spare.id))


def test_save_many__upserts_every_row(loaded: UowFactory) -> None:
    changed = [r.model_copy(update={"reputation": 1}) for r in WORLD.referees[:3]]
    with loaded() as uow:
        uow.referees.save_many(changed)
        assert uow.referees.count({"reputation": 1}) == 3


def test_meta_and_stage_log__round_trip(loaded: UowFactory) -> None:
    entry = StageLogEntry(date=dt.date(2031, 8, 15), stage="recovery", delta_hash="abc")
    with loaded() as uow:
        uow.meta.save(MetaEntry(key="note", value="hello"))
        uow.stage_log.save(entry)
        assert uow.meta.require("note").value == "hello"
        assert uow.stage_log.find({"date": dt.date(2031, 8, 15)}) == [entry]


def test_fixture_match_summary_and_events__round_trip(loaded: UowFactory) -> None:
    fixture = make_fixture(WORLD)
    match = make_match(WORLD, fixture)
    result = make_match_result()
    with loaded() as uow:
        uow.seasons.save(WORLD.seasons[0])
        uow.fixtures.save(fixture)
        uow.matches.save(match)
        uow.summaries.save(SummaryRecord(match_id=match.id, summary=result.summary))
        uow.events.append_many(
            [
                StoredEvent(match_id=match.id, seq=e.seq, type=e.type, tick=e.tick, event=e)
                for e in result.events
            ]
        )
        assert uow.matches.get(str(match.id)) == match
        assert uow.summaries.require(str(match.id)).summary == result.summary
        events = uow.events.find({"match_id": str(match.id)}, order_by="seq")
        assert [e.event for e in events] == list(result.events)
        assert uow.events.count({"type": "kickoff"}) == 1
        assert RepositoryWorldReader(uow).fixtures(str(fixture.season_id), 1) == [fixture]


# ---------------------------------------------------------------- append-only
def _entry(club: str, entry_id: str, amount: int) -> LedgerEntry:
    return LedgerEntry(
        id=Id(entry_id),
        club_id=ClubId(club),
        date=dt.date(2031, 8, 20),
        category=LedgerCategory.MATCHDAY,
        amount=amount,
        ref={"fixture": "fix_01"},
    )


def test_ledger__append_is_additive_and_a_duplicate_key_conflicts(loaded: UowFactory) -> None:
    club = WORLD.clubs[0]
    with loaded() as uow:
        before = uow.ledger.total("amount", {"club_id": str(club.id)})
        uow.ledger.append_many(
            [_entry(str(club.id), "led_x0001", 500), _entry(str(club.id), "led_x0002", -200)]
        )
        assert uow.ledger.total("amount", {"club_id": str(club.id)}) == before + 300
        assert uow.ledger.find({"ref_type": "fixture"})[0].id == "led_x0001"
        with pytest.raises(ConflictError):
            uow.ledger.append(_entry(str(club.id), "led_x0001", 1))


# ---------------------------------------------------------------- transactions
def _write_then_crash(factory: UowFactory) -> None:
    with factory() as uow:
        uow.meta.save(MetaEntry(key="a", value="1"))
        raise RuntimeError("boom")


def test_unit_of_work__exception_inside_the_block_rolls_everything_back(
    empty_backend: tuple[UowFactory, object],
) -> None:
    factory, _ = empty_backend
    with pytest.raises(RuntimeError, match="boom"):
        _write_then_crash(factory)
    with factory() as uow:
        assert uow.meta.count() == 0


def test_unit_of_work__leaving_without_commit_discards_writes(
    empty_backend: tuple[UowFactory, object],
) -> None:
    factory, _ = empty_backend
    with factory() as uow:
        uow.meta.save(MetaEntry(key="a", value="1"))
    with factory() as uow:
        assert uow.meta.get("a") is None


def test_unit_of_work__commit_persists_and_later_rollback_keeps_it(
    empty_backend: tuple[UowFactory, object],
) -> None:
    factory, _ = empty_backend
    with factory() as uow:
        uow.meta.save(MetaEntry(key="a", value="1"))
        uow.commit()
        uow.meta.save(MetaEntry(key="b", value="2"))
        uow.rollback()
        assert uow.meta.get("b") is None
    with factory() as uow:
        assert [m.key for m in uow.meta.all()] == ["a"]


def _commit_match_then_crash(factory: UowFactory) -> None:
    fixture = make_fixture(WORLD)
    match = make_match(WORLD, fixture)
    result = make_match_result()
    with factory() as uow:
        uow.fixtures.save(fixture)
        uow.matches.save(match)
        uow.events.append_many(
            [
                StoredEvent(match_id=match.id, seq=e.seq, type=e.type, tick=e.tick, event=e)
                for e in result.events
            ]
        )
        uow.ledger.append(_entry(str(WORLD.clubs[0].id), "led_x0001", 500))
        raise RuntimeError("crash before commit")


def test_unit_of_work__failed_match_commit_leaves_no_partial_state(
    empty_backend: tuple[UowFactory, object],
) -> None:
    """Atomicity: a match, its events and a ledger entry commit together or not at all."""
    factory, _ = empty_backend
    save_world(WORLD, factory())
    with pytest.raises(RuntimeError, match="crash"):
        _commit_match_then_crash(factory)
    with factory() as uow:
        assert uow.matches.count() == 0
        assert uow.events.count() == 0
        assert uow.fixtures.count() == 0
        assert uow.ledger.count() == len(WORLD.clubs)
