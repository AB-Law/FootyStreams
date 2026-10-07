from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import Any

import pytest

from footystreams.domain.rng import WorldRng
from footystreams.domain.weather import Daylight, Weather, WeatherCondition
from footystreams.league.attendance import CrowdInputs, attendance, fill_rate
from footystreams.league.climate import ClimateCatalog
from footystreams.league.weather_gen import generate_weather
from footystreams.seed.static.files import read_yaml
from tests.factories.league_config import make_league_config
from tests.factories.world import make_world

WEATHER = make_league_config().weather
ATTENDANCE = make_league_config().attendance
CLIMATE = ClimateCatalog.model_validate(read_yaml("climate.yaml"))
KICKOFF = dt.datetime(2031, 9, 12, 15)


def _weather(band: str, kickoff: dt.datetime, seed: int) -> Weather:
    return generate_weather(CLIMATE.bands[band], kickoff, WorldRng(seed), WEATHER)


@pytest.mark.parametrize("band", sorted(CLIMATE.bands))
def test_generate_weather__every_band_and_month__is_a_valid_weather(band: str) -> None:
    for month in range(1, 13):
        for seed in range(15):
            assert _weather(band, dt.datetime(2031, month, 10, 17), seed).condition is not None


def test_generate_weather__same_seed__same_weather() -> None:
    assert _weather("coastal", KICKOFF, 4) == _weather("coastal", KICKOFF, 4)


def test_generate_weather__summer_is_warmer_than_winter() -> None:
    summer = [
        _weather("temperate", dt.datetime(2031, 7, 10, 15), s).temperature_c for s in range(60)
    ]
    winter = [
        _weather("temperate", dt.datetime(2031, 1, 10, 15), s).temperature_c for s in range(60)
    ]
    assert sum(summer) / 60 > sum(winter) / 60 + 8


def test_generate_weather__rain_share__follows_the_bands_probability() -> None:
    wet = sum(_weather("highland", KICKOFF, s).rain_mm_per_h > 0 for s in range(400)) / 400
    dry = sum(_weather("warm", KICKOFF, s).rain_mm_per_h > 0 for s in range(400)) / 400
    assert wet > dry + 0.1


def test_generate_weather__freezing_precipitation__falls_as_snow() -> None:
    samples = [_weather("continental", dt.datetime(2031, 1, 10, 15), s) for s in range(300)]
    freezing = [
        w for w in samples if w.rain_mm_per_h and w.temperature_c < WEATHER.rain_temperature_limit
    ]
    assert freezing
    assert all(w.condition is WeatherCondition.SNOW for w in freezing)


@pytest.mark.parametrize(
    ("hour", "daylight"), [(13, Daylight.DAY), (17, Daylight.DUSK), (20, Daylight.NIGHT)]
)
def test_generate_weather__kickoff_hour__sets_daylight(hour: int, daylight: Daylight) -> None:
    assert _weather("temperate", dt.datetime(2031, 9, 12, hour), 1).daylight is daylight


def _inputs(**changes: Any) -> CrowdInputs:
    club = make_world(1).clubs[0]
    clear = _weather("warm", KICKOFF, 1).model_copy(update={"condition": WeatherCondition.CLEAR})
    base = CrowdInputs(
        stadium=club.stadium,
        fanbase=club.fanbase,
        reputation=50,
        form=0.5,
        derby=False,
        weather=clear,
    )
    return replace(base, **changes)


def test_fill_rate__better_reputation_and_form_and_derby__fill_more() -> None:
    base = fill_rate(_inputs(), ATTENDANCE)
    assert fill_rate(_inputs(reputation=90), ATTENDANCE) > base
    assert fill_rate(_inputs(form=0.9), ATTENDANCE) > base
    assert fill_rate(_inputs(derby=True), ATTENDANCE) > base


def test_fill_rate__bad_weather__keeps_people_home() -> None:
    storm = _weather("highland", KICKOFF, 1).model_copy(update={"condition": WeatherCondition.SNOW})
    assert fill_rate(_inputs(weather=storm), ATTENDANCE) < fill_rate(_inputs(), ATTENDANCE)


def test_attendance__always_between_the_floor_and_a_sell_out() -> None:
    inputs = _inputs()
    capacity = inputs.stadium.capacity
    for seed in range(80):
        crowd = attendance(inputs, WorldRng(seed), ATTENDANCE)
        assert round(capacity * ATTENDANCE.minimum_fill) <= crowd <= capacity


def test_attendance__same_seed__same_crowd() -> None:
    inputs = _inputs()
    assert attendance(inputs, WorldRng(3), ATTENDANCE) == attendance(
        inputs, WorldRng(3), ATTENDANCE
    )
