"""Training plan and development journal entries."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import GameDate, Position, Unit


class TrainingFocus(StrEnum):
    """Individual training focus."""

    ATTRIBUTE_GROUP = "attribute_group"
    POSITION_RETRAIN = "position_retrain"
    BALANCED = "balanced"


class TrainingPlan(DomainModel):
    """Per-player training focus."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "focus": "L",
        "retrain_position": "L",
        "intensity": "L",
    }

    focus: TrainingFocus = TrainingFocus.BALANCED
    retrain_position: Position | None = None
    intensity: Unit = 0.5


class DevelopmentEntry(DomainModel):
    """One explainable attribute change."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "date": "L",
        "attr": "L",
        "delta": "L",
        "cause": "L",
    }

    date: GameDate
    attr: str = Field(min_length=1, max_length=40)
    delta: int
    cause: str = Field(min_length=1, max_length=80)
