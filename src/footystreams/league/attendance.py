"""How many people come: capacity, standing, form, derbies and the weather (pure, seeded)."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.club import Fanbase
from footystreams.domain.rng import WorldRng
from footystreams.domain.stadium import Stadium
from footystreams.domain.weather import Weather, WeatherCondition
from footystreams.league.config import AttendanceConfig

REPUTATION_MIDPOINT = 50.0
REPUTATION_SPAN = 100.0
FORM_MIDPOINT = 0.5
BAD_WEATHER = frozenset(
    {
        WeatherCondition.HEAVY_RAIN,
        WeatherCondition.SNOW,
        WeatherCondition.FOG,
        WeatherCondition.WINDY,
    }
)


@dataclass(frozen=True, slots=True)
class CrowdInputs:
    """What draws a crowd to one match."""

    stadium: Stadium
    fanbase: Fanbase
    reputation: int
    form: float
    derby: bool
    weather: Weather


def fill_rate(inputs: CrowdInputs, config: AttendanceConfig) -> float:
    """Share of the seats expected to be taken, before noise and the floor."""
    fill = config.base_fill
    fill += config.reputation_weight * (inputs.reputation - REPUTATION_MIDPOINT) / REPUTATION_SPAN
    fickle = 1.0 + config.fickleness_weight * (inputs.fanbase.fickleness - FORM_MIDPOINT)
    fill += config.form_weight * (inputs.form - FORM_MIDPOINT) * fickle
    fill += config.derby_bonus if inputs.derby else 0.0
    if inputs.weather.condition in BAD_WEATHER:
        fill -= config.bad_weather_penalty * (1.0 - inputs.fanbase.passion)
    return fill


def attendance(inputs: CrowdInputs, rng: WorldRng, config: AttendanceConfig) -> int:
    """The crowd, between the minimum fill and a sell-out."""
    noisy = fill_rate(inputs, config) + rng.normal(0.0, config.noise)
    clamped = max(config.minimum_fill, min(1.0, noisy))
    return round(inputs.stadium.capacity * clamped)
