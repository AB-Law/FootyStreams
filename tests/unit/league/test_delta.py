from __future__ import annotations

from footystreams.domain.finance import LedgerCategory, LedgerEntry
from footystreams.domain.ids import derive_id
from footystreams.domain.types import ClubId
from footystreams.league.delta import WorldDelta, apply_delta, merge_all
from tests.factories.league_db import make_league_db
from tests.factories.mood import TODAY, make_modifier


def _ledger(amount: int, key: str = "a") -> LedgerEntry:
    return LedgerEntry(
        id=derive_id("ledger", key),
        club_id=ClubId("clb_00001"),
        date=TODAY,
        category=LedgerCategory.MATCHDAY,
        amount=amount,
    )


def test_world_delta__empty__reports_empty() -> None:
    assert WorldDelta().is_empty()
    assert not WorldDelta(modifiers=(make_modifier(),)).is_empty()


def test_world_delta__merge__concatenates_rows_in_order() -> None:
    first = WorldDelta(ledger=(_ledger(1, "a"),))
    second = WorldDelta(ledger=(_ledger(2, "b"),), modifiers=(make_modifier(),))
    merged = merge_all([first, second])
    assert [entry.amount for entry in merged.ledger] == [1, 2]
    assert len(merged.modifiers) == 1


def test_content_hash__same_rows__same_hash_and_different_rows__different_hash() -> None:
    assert (
        WorldDelta(ledger=(_ledger(5),)).content_hash()
        == WorldDelta(ledger=(_ledger(5),)).content_hash()
    )
    assert (
        WorldDelta(ledger=(_ledger(5),)).content_hash()
        != WorldDelta(ledger=(_ledger(6),)).content_hash()
    )


def test_apply_delta__upserts_and_appends_through_the_repositories() -> None:
    factory = make_league_db()
    delta = WorldDelta(modifiers=(make_modifier(),), ledger=(_ledger(7),))
    with factory() as uow:
        opening = uow.ledger.total("amount", {"club_id": "clb_00001"})
        apply_delta(uow, delta)
        uow.commit()
    with factory() as uow:
        assert [m.id for m in uow.modifiers.all()] == ["mod_00001"]
        assert uow.ledger.total("amount", {"club_id": "clb_00001"}) == opening + 7


def test_apply_delta__empty__writes_nothing() -> None:
    factory = make_league_db()
    with factory() as uow:
        apply_delta(uow, WorldDelta())
        assert uow.modifiers.count() == 0
