"""Match weather conditions."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import Unit


class WeatherCondition(StrEnum):
    """Weather band for a match."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    WINDY = "windy"
    FOG = "fog"
    SNOW = "snow"
    HOT = "hot"
    COLD = "cold"


class Daylight(StrEnum):
    """Daylight band."""

    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"


class Weather(DomainModel):
    """Frozen weather conditions for a match."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "condition": "S",
        "temperature_c": "S",
        "humidity": "S",
        "wind_speed_mps": "S",
        "wind_direction_deg": "S",
        "rain_mm_per_h": "S",
        "pitch_wetness": "S",
        "visibility": "S",
        "daylight": "S",
    }

    condition: WeatherCondition
    temperature_c: float = Field(ge=-10, le=42)
    humidity: Unit
    wind_speed_mps: float = Field(ge=0, le=20)
    wind_direction_deg: int = Field(ge=0, le=359)
    rain_mm_per_h: float = Field(ge=0, le=30)
    pitch_wetness: Unit
    visibility: Unit
    daylight: Daylight = Daylight.DAY
