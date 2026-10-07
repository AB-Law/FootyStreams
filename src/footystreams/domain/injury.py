"""Injury and discipline value objects on a player."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import GameDate


class InjurySeverity(StrEnum):
    """Apparent/clinical severity band."""

    KNOCK = "knock"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class Injury(DomainModel):
    """Current or historical injury episode."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "type": "S+L",
        "body_part": "S+L",
        "severity": "S+L",
        "started_on": "S+L",
        "expected_return_on": "S+L",
        "games_missed": "L",
    }

    type: str = Field(min_length=1, max_length=40)
    body_part: str = Field(min_length=1, max_length=40)
    severity: InjurySeverity
    started_on: GameDate
    expected_return_on: GameDate
    games_missed: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def _ordered_dates(self) -> Self:
        if self.expected_return_on < self.started_on:
            msg = "expected_return_on must be on or after started_on"
            raise ValueError(msg)
        return self


class InjuryRecord(DomainModel):
    """Past injury kept for proneness and storylines."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "type": "L",
        "body_part": "R",
        "severity": "L",
        "started_on": "L",
        "returned_on": "L",
        "games_missed": "L",
    }

    type: str = Field(min_length=1, max_length=40)
    body_part: str = Field(min_length=1, max_length=40)
    severity: InjurySeverity
    started_on: GameDate
    returned_on: GameDate
    games_missed: int = Field(ge=0, default=0)


class Suspension(DomainModel):
    """Outstanding match ban."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "matches_remaining": "L",
        "reason": "L",
    }

    matches_remaining: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=80)


class Discipline(DomainModel):
    """Season card tally and ban-threshold progress."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "yellows_season": "L",
        "reds_season": "L",
        "yellow_ban_threshold_progress": "L",
    }

    yellows_season: int = Field(ge=0, default=0)
    reds_season: int = Field(ge=0, default=0)
    yellow_ban_threshold_progress: int = Field(ge=0, default=0)


class MoraleFactor(DomainModel):
    """Explainable reason contributing to morale."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "L",
        "delta": "L",
        "expires_on": "L",
    }

    kind: str = Field(min_length=1, max_length=40)
    delta: float
    expires_on: GameDate | None = None
