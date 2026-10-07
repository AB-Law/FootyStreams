"""Cross-entity relationships."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import EntityRef, GameDate, RelationshipId, Signed, Unit


class Relationship(DomainModel):
    """Directed or mutual bond between two entities."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "R",
        "a": "R",
        "b": "R",
        "kind": "R",
        "strength": "R",
        "valence": "R",
        "since": "R",
        "public": "R",
    }

    id: RelationshipId
    a: EntityRef
    b: EntityRef
    kind: str = Field(min_length=1, max_length=40)
    strength: Unit
    valence: Signed = 0.0
    since: GameDate | None = None
    public: bool = False
