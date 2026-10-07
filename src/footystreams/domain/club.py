"""Club aggregate and embedded fanbase, board, facilities and academy."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field, field_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.finance import ClubFinances
from footystreams.domain.manager import Objective
from footystreams.domain.stadium import Stadium
from footystreams.domain.tactics import TeamTactics
from footystreams.domain.types import (
    ClubId,
    Disposition,
    Level,
    ManagerId,
    NationId,
    PlayerId,
    Reputation,
    StaffId,
    Unit,
)

DERBY_INTENSITY = 0.5
SHORT_CODE_LEN = 3


class KitPattern(StrEnum):
    """Kit visual pattern."""

    SOLID = "solid"
    STRIPES = "stripes"
    HOOPS = "hoops"
    HALVES = "halves"
    SASH = "sash"


class KitSpec(DomainModel):
    """Kit colours and pattern."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"pattern": "R", "colours": "R"}

    pattern: KitPattern = KitPattern.SOLID
    colours: tuple[str, ...] = ()


class ClubColours(DomainModel):
    """Primary identity colours and kits."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "primary": "R",
        "secondary": "R",
        "accent": "R",
        "home_kit": "R",
        "away_kit": "S",
    }

    primary: str
    secondary: str
    accent: str
    home_kit: KitSpec
    away_kit: KitSpec


class ClubLocation(DomainModel):
    """City identity for climate and fanbase sizing."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "city": "L",
        "region": "R",
        "nation_id": "L",
        "population": "L",
    }

    city: str = Field(min_length=1, max_length=80)
    region: str = ""
    nation_id: NationId
    population: int = Field(ge=0)


class Fanbase(DomainModel):
    """Club support profile."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "size": "L",
        "passion": "S+L",
        "toxicity": "S+L",
        "fickleness": "L",
        "away_following": "S+L",
        "traditions": "R",
    }

    size: int = Field(ge=0)
    passion: Unit
    toxicity: Unit
    fickleness: Unit
    away_following: Unit
    traditions: tuple[str, ...] = ()


class FacilityUpgrade(DomainModel):
    """Pending facility improvement."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "L",
        "to_level": "L",
        "cost": "L",
    }

    kind: str
    to_level: Level
    cost: int = Field(ge=0)


class Facilities(DomainModel):
    """Training, youth and medical facility levels."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "training": "L",
        "youth": "L",
        "medical": "L",
        "upgrades": "L",
    }

    training: Level
    youth: Level
    medical: Level
    upgrades: tuple[FacilityUpgrade, ...] = ()


class YouthAcademy(DomainModel):
    """Youth intake configuration."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "level": "L",
        "intake_size": "L",
        "intake_quality": "L",
        "philosophy_tag": "L",
        "prospect_ids": "L",
    }

    level: Level
    intake_size: int = Field(ge=0)
    intake_quality: Unit
    philosophy_tag: str = ""
    prospect_ids: tuple[PlayerId, ...] = ()


class Board(DomainModel):
    """Ownership / directors profile."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "ambition": "L",
        "patience": "L",
        "meddling": "R",
        "budget_strictness": "L",
        "expectations": "L",
        "manager_confidence": "L",
    }

    ambition: Disposition
    patience: Disposition
    meddling: Disposition
    budget_strictness: Disposition
    expectations: tuple[Objective, ...] = ()
    manager_confidence: Unit = 0.5


class Rivalry(DomainModel):
    """Derby / rivalry link to another club."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club_id": "S+L",
        "intensity": "S+L",
        "origin": "R",
        "label": "R",
    }

    club_id: ClubId
    intensity: Unit
    origin: str = ""
    label: str = ""

    @property
    def is_derby(self) -> bool:
        """True when intensity is high enough to flag fixtures as derbies."""
        return self.intensity >= DERBY_INTENSITY


class ClubCulture(DomainModel):
    """Soft cultural values and tags."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"values": "R", "tags": "R"}

    values: Mapping[str, Unit] = Field(default_factory=dict)
    tags: tuple[str, ...] = ()


class Club(DomainModel):
    """Club aggregate root."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "name": "L",
        "short_name": "L",
        "short_code": "L",
        "nickname": "R",
        "colours": "R",
        "crest_description": "R",
        "founded_year": "R",
        "location": "L",
        "stadium": "S",
        "fanbase": "S+L",
        "finances": "L",
        "facilities": "L",
        "academy": "L",
        "board": "L",
        "club_reputation": "S+L",
        "prestige": "R",
        "rivalries": "S+L",
        "culture": "R",
        "default_tactics": "S",
        "manager_id": "L",
        "staff_ids": "L",
    }

    id: ClubId
    name: str = Field(min_length=1, max_length=80)
    short_name: str = Field(min_length=1, max_length=40)
    short_code: str
    nickname: str = ""
    colours: ClubColours
    crest_description: str = ""
    founded_year: int = Field(ge=1800, le=2100)
    location: ClubLocation
    stadium: Stadium
    fanbase: Fanbase
    finances: ClubFinances
    facilities: Facilities
    academy: YouthAcademy
    board: Board
    club_reputation: Reputation
    prestige: Reputation = 50
    rivalries: tuple[Rivalry, ...] = ()
    culture: ClubCulture = Field(default_factory=ClubCulture)
    default_tactics: TeamTactics
    manager_id: ManagerId | None = None
    staff_ids: tuple[StaffId, ...] = ()

    @field_validator("short_code")
    @classmethod
    def _three_letter_code(cls, value: str) -> str:
        if len(value) != SHORT_CODE_LEN or not value.isalpha() or not value.isupper():
            msg = "short_code must be three uppercase letters"
            raise ValueError(msg)
        return value
