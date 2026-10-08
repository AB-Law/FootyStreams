"""A transfer is atomic: if any part of the day's delta fails to write, none of it is kept."""

from __future__ import annotations

import datetime as dt
from typing import ClassVar

import pytest

from footystreams.domain.finance import LedgerCategory
from footystreams.domain.transfer import Transfer
from footystreams.domain.types import Id
from footystreams.league.daily import DailyTick
from footystreams.league.delta import WorldDelta
from footystreams.league.ledger import Posting, book
from footystreams.persistence.memory_impl import MemoryAppendOnly
from tests.factories.league_db import make_league_db
from tests.factories.league_run import make_engine

pytestmark = pytest.mark.timeout(120)
DAY = dt.date(2031, 7, 1)


class _OneTransfer:
    """A stage that moves a player between two clubs and books both legs of the fee."""

    name: ClassVar[str] = "one_transfer"

    def run(self, repositories, today, rng):  # type: ignore[no-untyped-def]
        clubs = repositories.clubs.all()
        buyer, seller = clubs[0], clubs[1]
        player = next(p for p in repositories.players.find({"club_id": seller.id}) if p.contract)
        moved = player.model_copy(
            update={"contract": player.contract.model_copy(update={"club_id": buyer.id})}
        )
        ref = {"transfer_id": "trf_atomic001"}
        legs = book(
            {c.id: c for c in clubs},
            [
                Posting(
                    buyer.id, today, LedgerCategory.TRANSFER_FEES, -1_000_000, "transfer_fee", ref
                ),
                Posting(
                    seller.id, today, LedgerCategory.PLAYER_SALES, 1_000_000, "player_sale", ref
                ),
            ],
        )
        transfer = Transfer(
            id=Id("trf_atomic001"),
            player_id=player.id,
            from_club_id=seller.id,
            to_club_id=buyer.id,
            fee=1_000_000,
            completed_on=today,
        )
        return WorldDelta(
            players=(moved,), clubs=legs.clubs, ledger=legs.ledger, transfers=(transfer,)
        )


def _snapshot(factory) -> tuple[int, int, int, int]:  # type: ignore[no-untyped-def]
    with factory() as uow:
        return (
            uow.transfers.count(),
            uow.ledger.count(),
            uow.stage_log.count(),
            sum(p.contract.club_id == "clb_00001" for p in uow.players.all() if p.contract),
        )


def test_a_failure_while_writing_the_ledger_leaves_no_trace_of_the_transfer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = make_league_db(2, 4)
    tick = DailyTick(factory, make_engine(2), [_OneTransfer()])
    before = _snapshot(factory)

    def boom(self: object, entities: object) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(MemoryAppendOnly, "append_many", boom)
    with pytest.raises(OSError, match="disk full"):
        tick.run_day()
    assert _snapshot(factory) == before


def test_without_the_failure_the_same_stage_writes_everything_together() -> None:
    factory = make_league_db(2, 4)
    tick = DailyTick(factory, make_engine(2), [_OneTransfer()])
    before = _snapshot(factory)
    tick.run_day()
    after = _snapshot(factory)
    assert after[0] == before[0] + 1
    assert after[1] == before[1] + 2
    assert after[2] == before[2] + 1
    assert after[3] == before[3] + 1
