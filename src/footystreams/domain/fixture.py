"""Fixture scheduling models."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import (
    ClubId,
    CompetitionId,
    FixtureId,
    GameDate,
    MatchId,
    SeasonId,
    StadiumId,
)


class FixtureStatus(StrEnum):
    """Lifecycle of a scheduled fixture."""

    SCHEDULED = "scheduled"
    PLAYED = "played"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class Fixture(DomainModel):
    """One scheduled pairing on a matchday."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "competition_id": "L",
        "season_id": "L",
        "matchday": "L",
        "date": "L",
        "home_club_id": "L",
        "away_club_id": "L",
        "stadium_id": "L",
        "is_derby": "S",
        "status": "L",
        "match_id": "L",
    }

    id: FixtureId
    competition_id: CompetitionId
    season_id: SeasonId
    matchday: int = Field(ge=1)
    date: GameDate
    home_club_id: ClubId
    away_club_id: ClubId
    stadium_id: StadiumId
    is_derby: bool = False
    status: FixtureStatus = FixtureStatus.SCHEDULED
    match_id: MatchId | None = None
