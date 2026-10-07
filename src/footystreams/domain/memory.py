"""Memory records (schema only in M1)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import EntityRef, GameDate, Id, MemoryId


class MemoryRecord(DomainModel):
    """One memory owned by an entity; schema only until the LLM layer."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "R",
        "owner": "R",
        "kind": "R",
        "created_on": "R",
        "summary_key": "R",
        "facts": "R",
        "related_ids": "R",
        "salience": "R",
    }

    id: MemoryId
    owner: EntityRef
    kind: str = Field(min_length=1, max_length=40)
    created_on: GameDate
    summary_key: str = Field(min_length=1, max_length=80)
    facts: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    related_ids: tuple[Id, ...] = ()
    salience: float = Field(ge=0.0, le=1.0, default=0.5)
