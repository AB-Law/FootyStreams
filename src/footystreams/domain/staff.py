"""StaffMember person kind."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.contract import Contract
from footystreams.domain.person import Person
from footystreams.domain.types import Attribute, ClubId, Level


class StaffRole(StrEnum):
    """Staff role at a club."""

    ASSISTANT_MANAGER = "assistant_manager"
    FIRST_TEAM_COACH = "first_team_coach"
    GOALKEEPING_COACH = "goalkeeping_coach"
    FITNESS_COACH = "fitness_coach"
    PHYSIO = "physio"
    SCOUT = "scout"
    ANALYST = "analyst"
    YOUTH_COACH = "youth_coach"


class StaffAttrs(DomainModel):
    """Staff skill attributes."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "coaching_technical": "L",
        "coaching_mental": "L",
        "coaching_physical": "L",
        "tactical_input": "S",
        "injury_treatment": "S+L",
        "injury_prevention": "L",
        "scouting_judgement": "L",
        "scouting_network": "R",
    }

    coaching_technical: Attribute
    coaching_mental: Attribute
    coaching_physical: Attribute
    tactical_input: Attribute
    injury_treatment: Attribute
    injury_prevention: Attribute
    scouting_judgement: Attribute
    scouting_network: Attribute


class StaffMember(Person):
    """Club staff member."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        **Person.__usage__,
        "club_id": "L",
        "role": "L",
        "quality": "L",
        "attrs": "S",
        "contract": "L",
    }

    club_id: ClubId
    role: StaffRole
    quality: Level
    attrs: StaffAttrs
    contract: Contract | None = None
