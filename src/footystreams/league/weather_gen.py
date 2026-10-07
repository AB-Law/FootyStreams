"""Match-day weather from a climate band, the date and the kick-off hour (pure, seeded)."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.rng import WorldRng
from footystreams.domain.weather import Daylight, Weather, WeatherCondition
from footystreams.league.climate import ClimateBand
from footystreams.league.config import WeatherConfig

TEMPERATURE_RANGE = (-9.0, 41.0)  # inside the Weather model's bounds
HEAVY_RAIN_MM = 4.0
LIGHT_RAIN_RANGE = (0.5, 3.5)
HEAVY_RAIN_RANGE = (4.0, 12.0)
HEAVY_SHARE = 0.3  # of rainy days
WINDY_MPS = 9.0
MAX_WIND_MPS = 19.0
CLOUDY_BASE = 0.35  # chance of cloud on a dry day, plus the band's humidity share
CLOUDY_HUMIDITY_SHARE = 0.4
DUSK_HOURS = 2
FULL_CIRCLE = 360
DRY_PITCH = 0.1
WET_PITCH_BASE = 0.55
WET_PITCH_PER_MM = 0.04
SNOW_VISIBILITY = 0.7
RAIN_VISIBILITY = 0.9
FOG_VISIBILITY = 0.5
FOG_HUMIDITY = 0.75
FOG_TEMPERATURE = 6.0
FOG_CHANCE = 0.25


def _daylight(hour: int, config: WeatherConfig) -> Daylight:
    if hour >= config.night_hour:
        return Daylight.NIGHT
    if hour >= config.night_hour - DUSK_HOURS:
        return Daylight.DUSK
    return Daylight.DAY


def _precipitation(band: ClimateBand, rng: WorldRng) -> float:
    """Millimetres per hour; 0.0 on a dry day."""
    if not rng.bernoulli(band.rain_probability):
        return 0.0
    low, high = HEAVY_RAIN_RANGE if rng.bernoulli(HEAVY_SHARE) else LIGHT_RAIN_RANGE
    return round(rng.uniform(low, high), 1)


def _wet_condition(
    precipitation: float, temperature: float, config: WeatherConfig
) -> WeatherCondition:
    if temperature < config.rain_temperature_limit:
        return WeatherCondition.SNOW
    return (
        WeatherCondition.HEAVY_RAIN
        if precipitation >= HEAVY_RAIN_MM
        else WeatherCondition.LIGHT_RAIN
    )


def _dry_condition(
    temperature: float, wind: float, config: WeatherConfig, sky: tuple[bool, bool]
) -> WeatherCondition:
    """The label of a dry day; ``sky`` is (cloudy, foggy)."""
    cloudy, foggy = sky
    if foggy:
        return WeatherCondition.FOG
    if wind >= WINDY_MPS:
        return WeatherCondition.WINDY
    if temperature >= config.hot_threshold:
        return WeatherCondition.HOT
    if temperature <= config.cold_threshold:
        return WeatherCondition.COLD
    return WeatherCondition.CLOUDY if cloudy else WeatherCondition.CLEAR


def _visibility(condition: WeatherCondition) -> float:
    if condition is WeatherCondition.FOG:
        return FOG_VISIBILITY
    if condition is WeatherCondition.SNOW:
        return SNOW_VISIBILITY
    if condition in {WeatherCondition.LIGHT_RAIN, WeatherCondition.HEAVY_RAIN}:
        return RAIN_VISIBILITY
    return 1.0


def generate_weather(
    band: ClimateBand, kickoff: dt.datetime, rng: WorldRng, config: WeatherConfig
) -> Weather:
    """The weather at ``kickoff`` in a place with this climate."""
    low, high = TEMPERATURE_RANGE
    temperature = round(
        max(
            low,
            min(
                high,
                band.monthly_temp_c[kickoff.month - 1] + rng.normal(0.0, config.temperature_noise),
            ),
        ),
        1,
    )
    wind = round(max(0.0, min(MAX_WIND_MPS, rng.normal(band.wind_mean_mps, config.wind_noise))), 1)
    precipitation = _precipitation(band, rng)
    cloudy = rng.bernoulli(CLOUDY_BASE + CLOUDY_HUMIDITY_SHARE * band.humidity)
    foggy = (
        band.humidity >= FOG_HUMIDITY
        and temperature <= FOG_TEMPERATURE
        and rng.bernoulli(FOG_CHANCE)
    )
    condition = (
        _wet_condition(precipitation, temperature, config)
        if precipitation
        else _dry_condition(temperature, wind, config, (cloudy, foggy))
    )
    wet = WET_PITCH_BASE + WET_PITCH_PER_MM * precipitation if precipitation else DRY_PITCH
    return Weather(
        condition=condition,
        temperature_c=temperature,
        humidity=band.humidity,
        wind_speed_mps=wind,
        wind_direction_deg=rng.u_int(FULL_CIRCLE),
        rain_mm_per_h=precipitation,
        pitch_wetness=round(min(1.0, wet), 2),
        visibility=_visibility(condition),
        daylight=_daylight(kickoff.hour, config),
    )
