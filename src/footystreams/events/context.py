"""Causal event context (no hindsight)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import Signed, Unit


class ContextTag(StrEnum):
    """Causal tags attachable at emit time."""

    COUNTER = "counter"
    SET_PIECE = "set_piece"
    PRESSURE = "pressure"
    TRANSITION = "transition"
    OPEN_PLAY = "open_play"


class EventContext(DomainModel):
    """Information available at the moment of the event."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "score_home": "S",
        "score_away": "S",
        "phase": "S",
        "momentum": "S",
        "intensity": "S",
        "significance": "S",
        "men_home": "S",
        "men_away": "S",
        "tags": "S",
        "headline": "S",
        "attack_dir": "S",
    }

    score_home: int = Field(ge=0, default=0)
    score_away: int = Field(ge=0, default=0)
    phase: str = "open_play"
    momentum: Signed = 0.0
    intensity: Unit = 0.5
    significance: Unit = 0.0
    men_home: int = Field(ge=0, le=11, default=11)
    men_away: int = Field(ge=0, le=11, default=11)
    tags: tuple[ContextTag, ...] = ()
    headline: str | None = None
    attack_dir: int = Field(ge=-1, le=1, default=1)
