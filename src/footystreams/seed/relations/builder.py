"""Shared builder for relationship rows: canonical order, unique ids, no self-links."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.ids import IdMint
from footystreams.domain.relationship import Relationship
from footystreams.domain.types import EntityKind, EntityRef, Id, RelationshipId

SYMMETRIC_KINDS = frozenset({"friend", "rival", "family", "colleague", "feud", "teammate_bond"})
# Kinds the public already knows about (commentary may mention them).
PUBLIC_KINDS = frozenset({"family", "feud", "colleague"})


class RelationshipBuilder:
    """Collects relationships; symmetric kinds are put in canonical order, duplicates dropped.

    Mutable on purpose: it accumulates the graph and remembers which pairs exist.
    """

    def __init__(self, ids: IdMint, since: dt.date) -> None:
        """Start an empty graph whose rows are dated ``since``."""
        self._ids = ids
        self._since = since
        self._rows: list[Relationship] = []
        self._seen: set[tuple[str, str, str]] = set()

    def ref(self, kind: EntityKind, entity_id: str) -> EntityRef:
        """An EntityRef for an id string."""
        return EntityRef(kind=kind, id=Id(entity_id))

    def add(
        self,
        kind: str,
        a: EntityRef,
        b: EntityRef,
        strength: float,
        valence: float = 0.0,
    ) -> bool:
        """Add a relationship; returns False when it was a self-link or already existed."""
        if a == b:
            return False
        first, second = (b, a) if kind in SYMMETRIC_KINDS and b.id < a.id else (a, b)
        key = (kind, first.id, second.id)
        if key in self._seen:
            return False
        self._seen.add(key)
        self._rows.append(
            Relationship(
                id=RelationshipId(self._ids.next("relationship")),
                a=first,
                b=second,
                kind=kind,
                strength=strength,
                valence=valence,
                since=self._since,
                public=kind in PUBLIC_KINDS,
            )
        )
        return True

    def rows(self) -> tuple[Relationship, ...]:
        """All relationships so far, in insertion order."""
        return tuple(self._rows)
