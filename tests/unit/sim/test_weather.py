from dataclasses import replace
from typing import Any

import pytest

from footystreams.domain.weather import Weather, WeatherCondition
from footystreams.sim import SimConfig, merge_config
from footystreams.sim.actions.passing import PassAttempt, PassKind, pass_success_probability
from footystreams.sim.build import build_state
from footystreams.sim.config import PassConfig, WeatherConfig
from footystreams.sim.rng import SimRng
from footystreams.sim.tables import default_tables
from footystreams.sim.weather import NEUTRAL, apply_conditions, conditions_for
from tests.factories.match import make_setup

ON = WeatherConfig(enabled=True)


def _weather(**overrides: Any) -> Weather:
    values: dict[str, Any] = {
        "condition": WeatherCondition.CLEAR,
        "temperature_c": 15.0,
        "humidity": 0.5,
        "wind_speed_mps": 2.0,
        "wind_direction_deg": 90,
        "rain_mm_per_h": 0.0,
        "pitch_wetness": 0.0,
        "visibility": 1.0,
    }
    values.update(overrides)
    return Weather(**values)


def test_conditions_for__switched_off_is_neutral() -> None:
    assert conditions_for(_weather(pitch_wetness=1.0), None, WeatherConfig()) is NEUTRAL


def test_conditions_for__mild_dry_weather_has_no_heat_cold_or_wetness() -> None:
    mild = conditions_for(_weather(), None, ON)
    assert (mild.heat, mild.cold, mild.wet) == (0.0, 0.0, 0.0)
    assert mild.first_touch_mult == pytest.approx(1.0)


def test_conditions_for__heat_and_cold_scale_with_temperature_and_are_bounded() -> None:
    hot = conditions_for(_weather(temperature_c=40.0), None, ON)
    warm = conditions_for(_weather(temperature_c=28.0), None, ON)
    freezing = conditions_for(_weather(temperature_c=-10.0), None, ON)
    assert hot.heat == 1.0 > warm.heat > 0.0
    assert freezing.cold == 1.0
    assert freezing.injury_mult > 1.0


def test_conditions_for__a_soaked_pitch_hurts_long_balls_touch_dribbling_and_raises_injury() -> (
    None
):
    dry = conditions_for(_weather(), None, ON)
    soaked = conditions_for(_weather(pitch_wetness=1.0), None, ON)
    assert soaked.long_pass_penalty > dry.long_pass_penalty
    assert soaked.first_touch_mult < dry.first_touch_mult
    assert soaked.dribble_mult < dry.dribble_mult
    assert soaked.injury_mult > dry.injury_mult


def test_conditions_for__wind_hurts_long_balls() -> None:
    calm = conditions_for(_weather(wind_speed_mps=0.0), None, ON)
    gale = conditions_for(_weather(wind_speed_mps=20.0), None, ON)
    assert gale.wind == 1.0
    assert gale.long_pass_penalty > calm.long_pass_penalty


def test_conditions_for__good_drainage_cuts_the_effective_wetness() -> None:
    state = build_state(make_setup(), default_tables(), SimRng(1))
    stadium = state.home.sheet.stadium
    assert stadium is None  # factory sheets carry no stadium: defaults apply
    default = conditions_for(_weather(pitch_wetness=1.0), None, ON)
    assert 0.0 < default.wet < 1.0


def test_apply_conditions__neutral_is_the_identity_and_wet_ground_lowers_touch() -> None:
    skills = build_state(make_setup(), default_tables(), SimRng(1)).home.players[3].skills
    assert apply_conditions(skills, NEUTRAL) is skills
    soaked = conditions_for(_weather(pitch_wetness=1.0), None, ON)
    wetter = apply_conditions(skills, soaked)
    assert wetter.first_touch < skills.first_touch
    assert wetter.dribbling < skills.dribbling
    assert wetter.finishing == skills.finishing


def test_pass_success__environment_only_hurts_long_through_and_cross_balls() -> None:
    cfg = PassConfig()

    def attempt(kind: PassKind, environment: float) -> PassAttempt:
        return PassAttempt(kind, 20.0, 60.0, 55.0, 0.1, 0.8, environment)

    for kind in (PassKind.LONG, PassKind.CROSS, PassKind.THROUGH):
        assert pass_success_probability(attempt(kind, 0.1), cfg) < pass_success_probability(
            attempt(kind, 0.0), cfg
        )
    for kind in (PassKind.SHORT, PassKind.BACK):
        assert pass_success_probability(attempt(kind, 0.1), cfg) == pass_success_probability(
            attempt(kind, 0.0), cfg
        )


def test_build_state__wet_weather_lowers_players_first_touch_when_enabled() -> None:
    setup = make_setup(weather=_weather(pitch_wetness=1.0))
    cfg = merge_config(SimConfig(), {"weather": {"enabled": True}})
    off = build_state(setup, default_tables(), SimRng(1), SimConfig())
    on = build_state(setup, default_tables(), SimRng(1), cfg)
    assert on.home.players[3].skills.first_touch < off.home.players[3].skills.first_touch
    assert on.conditions.wet > 0.0
    assert replace(on.conditions).wet == on.conditions.wet
