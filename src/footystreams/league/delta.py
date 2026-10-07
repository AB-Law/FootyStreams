"""``WorldDelta``: everything one stage or one match changes, as data.

Pure league functions never write. They read a ``WorldReader`` and return a delta; the runner
applies it inside a unit of work (one transaction per match and per daily-tick stage). A delta is
hashable by content, which is how a stage is shown to be idempotent (the ``world_log`` row).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING

from footystreams.domain.canonical import canonical_json

if TYPE_CHECKING:
    from footystreams.domain.club import Club
    from footystreams.domain.competition import Season
    from footystreams.domain.finance import LedgerEntry
    from footystreams.domain.fixture import Fixture
    from footystreams.domain.match import Match
    from footystreams.domain.mood import StateModifier, WorldEvent
    from footystreams.domain.player import Player
    from footystreams.domain.world import SquadEntry
    from footystreams.persistence.ports import (
        MetaEntry,
        Repositories,
        StandingsSnapshot,
        StoredEvent,
        SummaryRecord,
    )

APPEND_ONLY = frozenset({"ledger", "events"})  # the field names written with append, not save


@dataclass(frozen=True, slots=True)
class WorldDelta:
    """Rows to upsert (or, for ``ledger`` and ``events``, append). Field names are table names.

    ``deletions`` lists ``(table, key)`` rows to remove; they are applied before the upserts so a
    freed unique value (a shirt number) can be reused in the same delta.
    """

    players: tuple[Player, ...] = ()
    clubs: tuple[Club, ...] = ()
    modifiers: tuple[StateModifier, ...] = ()
    world_events: tuple[WorldEvent, ...] = ()
    fixtures: tuple[Fixture, ...] = ()
    matches: tuple[Match, ...] = ()
    summaries: tuple[SummaryRecord, ...] = ()
    standings: tuple[StandingsSnapshot, ...] = ()
    ledger: tuple[LedgerEntry, ...] = ()
    events: tuple[StoredEvent, ...] = ()
    seasons: tuple[Season, ...] = ()
    squad_entries: tuple[SquadEntry, ...] = ()
    meta: tuple[MetaEntry, ...] = ()
    deletions: tuple[tuple[str, str], ...] = ()  # (table, key) rows to remove, applied first

    def is_empty(self) -> bool:
        """True when the delta changes nothing."""
        return not any(getattr(self, field.name) for field in fields(self))

    def merge(self, other: WorldDelta) -> WorldDelta:
        """This delta followed by ``other`` (rows of ``other`` win on the same key when applied)."""
        return replace(
            self, **{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)}
        )

    def content_hash(self) -> str:
        """SHA-256 over the canonical JSON of every row, in field and row order."""
        document: dict[str, object] = {
            field.name: [row.model_dump(mode="json") for row in getattr(self, field.name)]
            for field in fields(self)
            if field.name != "deletions"
        }
        document["deletions"] = [list(item) for item in self.deletions]
        return hashlib.sha256(canonical_json(document).encode()).hexdigest()


def merge_all(deltas: list[WorldDelta]) -> WorldDelta:
    """All deltas in order, as one."""
    merged = WorldDelta()
    for delta in deltas:
        merged = merged.merge(delta)
    return merged


def apply_delta(repositories: Repositories, delta: WorldDelta) -> None:
    """Write the delta through the repositories (the caller owns the transaction)."""
    for table, key in delta.deletions:
        getattr(repositories, table).delete(key)
    for field in fields(delta):
        if field.name == "deletions":
            continue
        rows = getattr(delta, field.name)
        if not rows:
            continue
        target = getattr(repositories, field.name)
        if field.name in APPEND_ONLY:
            target.append_many(rows)
        else:
            target.save_many(rows)
