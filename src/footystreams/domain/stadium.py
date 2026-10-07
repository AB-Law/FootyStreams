"""Stadium and pitch models."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import GameDate, Money, Unit

MIN_CAPACITY = 5_000
MAX_CAPACITY = 80_000
MIN_PITCH_LENGTH_M = 100
MAX_PITCH_LENGTH_M = 110
MIN_PITCH_WIDTH_M = 64
MAX_PITCH_WIDTH_M = 75


class PitchSurface(StrEnum):
    """Playing surface type."""

    GRASS = "grass"
    HYBRID = "hybrid"
    ARTIFICIAL = "artificial"


class RoofType(StrEnum):
    """Stadium roof coverage."""

    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"


class UpgradeStatus(StrEnum):
    """Stadium works status."""

    NONE = "none"
    PLANNED = "planned"
    BUILDING = "building"


class Pitch(DomainModel):
    """Pitch dimensions and quality."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "length_m": "S",
        "width_m": "S",
        "quality": "S",
        "surface": "S",
        "drainage": "S",
        "quirks": "R",
    }

    length_m: int = Field(ge=MIN_PITCH_LENGTH_M, le=MAX_PITCH_LENGTH_M)
    width_m: int = Field(ge=MIN_PITCH_WIDTH_M, le=MAX_PITCH_WIDTH_M)
    quality: Unit
    surface: PitchSurface = PitchSurface.GRASS
    drainage: Unit = 0.5
    quirks: tuple[str, ...] = ()


class HomeAdvantageFactors(DomainModel):
    """Per-stadium scaling of home-advantage channels."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "crowd_weight": "S",
        "referee_pressure_weight": "S",
        "familiarity_weight": "S",
        "travel_weight": "S",
    }

    crowd_weight: Unit = 0.5
    referee_pressure_weight: Unit = 0.5
    familiarity_weight: Unit = 0.5
    travel_weight: Unit = 0.5


class StadiumUpgrade(DomainModel):
    """Planned or in-progress capacity works."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "planned_capacity": "L",
        "cost": "L",
        "started_on": "L",
        "completes_on": "L",
        "status": "L",
    }

    planned_capacity: int = Field(ge=MIN_CAPACITY, le=MAX_CAPACITY)
    cost: Money = Field(ge=0)
    started_on: GameDate | None = None
    completes_on: GameDate | None = None
    status: UpgradeStatus = UpgradeStatus.NONE


class Stadium(DomainModel):
    """Home ground of a club."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "name": "R",
        "nickname": "R",
        "capacity": "S+L",
        "pitch": "S",
        "atmosphere": "S",
        "proximity": "S",
        "roof": "R",
        "altitude_m": "S",
        "home_advantage": "S",
        "ticket_price_base": "L",
        "upgrade": "L",
    }

    name: str = Field(min_length=1, max_length=80)
    nickname: str = ""
    capacity: int = Field(ge=MIN_CAPACITY, le=MAX_CAPACITY)
    pitch: Pitch
    atmosphere: Unit
    proximity: Unit
    roof: RoofType = RoofType.OPEN
    altitude_m: int = 0
    home_advantage: HomeAdvantageFactors = Field(default_factory=HomeAdvantageFactors)
    ticket_price_base: Money = Field(ge=0, default=0)
    upgrade: StadiumUpgrade | None = None
