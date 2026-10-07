"""Player and manager contract value objects."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import ClubId, GameDate, Money, Unit


class SquadRole(StrEnum):
    """Playing-time promise encoded in a contract."""

    KEY = "key"
    ROTATION = "rotation"
    PROSPECT = "prospect"
    BACKUP = "backup"


class Contract(DomainModel):
    """Employment terms for a player at a club."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club_id": "L",
        "start": "L",
        "end": "L",
        "wage_weekly": "L",
        "signing_bonus": "L",
        "appearance_bonus": "L",
        "goal_bonus": "L",
        "clean_sheet_bonus": "L",
        "release_clause": "L",
        "sell_on_pct": "L",
        "squad_role": "L",
        "extension_option": "L",
        "relegation_wage_cut_pct": "R",
    }

    club_id: ClubId
    start: GameDate
    end: GameDate
    wage_weekly: Money = Field(ge=0)
    signing_bonus: Money = Field(ge=0, default=0)
    appearance_bonus: Money = Field(ge=0, default=0)
    goal_bonus: Money = Field(ge=0, default=0)
    clean_sheet_bonus: Money = Field(ge=0, default=0)
    release_clause: Money | None = None
    sell_on_pct: Unit = 0.0
    squad_role: SquadRole = SquadRole.ROTATION
    extension_option: bool = False
    relegation_wage_cut_pct: Unit = 0.0
