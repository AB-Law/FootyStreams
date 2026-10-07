"""Shared frozen Pydantic base and field-usage tagging for domain models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

UsageTag = Literal["S", "L", "R", "S+L"]


class DomainModel(BaseModel):
    """Immutable domain value/object with forbid-extra and S/L/R usage tags.

    Collection fields on subclasses must use ``tuple`` / ``Mapping`` (not
    ``list`` / ``dict``): ``frozen=True`` does not freeze mutable containers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    __usage__: ClassVar[Mapping[str, UsageTag]] = {}
