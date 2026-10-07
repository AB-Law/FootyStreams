"""Mood resolution output and (later) state-modifier entities.

``ResolvedMood`` is defined here for PlayerSnapshot (slice 10). StateModifier
and WorldEvent land in the world/transfer slice.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import Id, Unit

# O3 defaults — mood.yaml (M2/M9) will own the live tunables.
DEFAULT_MENTAL_PENALTY_CAP = 0.20
DEFAULT_TECHNICAL_PENALTY_CAP = 0.10
DEFAULT_PHYSICAL_PENALTY_CAP = 0.05
DEFAULT_MENTAL_BONUS_CAP = 0.06
DEFAULT_TECHNICAL_BONUS_CAP = 0.03
DEFAULT_PHYSICAL_BONUS_CAP = 0.01


class ResolvedMood(DomainModel):
    """Frozen mood multipliers copied into a PlayerSnapshot before kickoff."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "mental_mult": "S",
        "technical_mult": "S",
        "physical_mult": "S",
        "volatility_add": "S",
        "contributing_modifier_ids": "S",
        "public_storyline_keys": "S",
    }

    mental_mult: float = Field(default=1.0)
    technical_mult: float = Field(default=1.0)
    physical_mult: float = Field(default=1.0)
    volatility_add: Unit = 0.0
    contributing_modifier_ids: tuple[Id, ...] = ()
    public_storyline_keys: tuple[str, ...] = ()
