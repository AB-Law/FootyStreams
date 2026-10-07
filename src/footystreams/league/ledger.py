"""Postings and bookkeeping: the one way money moves (docs/design: ledger is append-only).

A ``Posting`` says what happened to a club's money. ``book`` turns postings into ledger entries and
moves the cached ``finances.balance`` by exactly their sum, so ``balance == opening + sum(ledger)``
holds after every stage by construction.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from footystreams.domain.club import Club
from footystreams.domain.finance import LedgerCategory, LedgerEntry
from footystreams.domain.ids import derive_id
from footystreams.domain.types import ClubId, Id, Money
from footystreams.league.delta import WorldDelta


@dataclass(frozen=True, slots=True)
class Posting:
    """A signed money movement for a club on a date (income positive, spending negative)."""

    club_id: ClubId
    date: dt.date
    category: LedgerCategory
    amount: Money
    memo_key: str
    ref: Mapping[str, str] = field(default_factory=dict)

    def entry(self) -> LedgerEntry:
        """The ledger row; its id depends only on what it is about, so a re-run repeats it."""
        parts = (self.club_id, self.date.isoformat(), self.category.value, self.memo_key)
        refs = tuple(f"{key}={value}" for key, value in sorted(self.ref.items()))
        return LedgerEntry(
            id=Id(derive_id("ledger", *parts, *refs)),
            club_id=self.club_id,
            date=self.date,
            category=self.category,
            amount=self.amount,
            ref=dict(self.ref),
            memo_key=self.memo_key,
        )


def book(clubs: Mapping[ClubId, Club], postings: Iterable[Posting]) -> WorldDelta:
    """Ledger entries for the postings and the clubs with their balances moved by the same sums."""
    entries: list[LedgerEntry] = []
    moved: dict[ClubId, int] = defaultdict(int)
    dates: dict[ClubId, dt.date] = {}
    for posting in postings:
        if posting.amount == 0:
            continue
        entries.append(posting.entry())
        moved[posting.club_id] += posting.amount
        dates[posting.club_id] = max(posting.date, dates.get(posting.club_id, posting.date))
    updated = [
        clubs[club_id].model_copy(
            update={
                "finances": clubs[club_id].finances.model_copy(
                    update={
                        "balance": clubs[club_id].finances.balance + moved[club_id],
                        "last_reconciled_on": dates[club_id],
                    }
                )
            }
        )
        for club_id in sorted(moved)
    ]
    return WorldDelta(clubs=tuple(updated), ledger=tuple(entries))
