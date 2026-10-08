"""Weather and pitch conditions as a handful of bounded numbers, computed once per match.

`conditions_for` folds temperature, rain, wind and the pitch (quality, drainage) into `Conditions`.
Components read the numbers they need: passing (long-ball penalty), skills (first touch,
dribbling), fatigue (heat, wetness) and injuries (hazard). With the weather switched off the
conditions are neutral. Pure functions (docs/design/02 section 10).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from footystreams.domain.stadium import Stadium
from footystreams.domain.weather import Weather
from footystreams.sim.config_world import WeatherConfig
from footystreams.sim.effective import Skills
from footystreams.sim.mathx import clamp


@dataclass(frozen=True, slots=True)
class Conditions:
    """Bounded effects of the weather and pitch (all in [0, 1] unless noted)."""

    heat: float  # 0 mild .. 1 sweltering
    cold: float  # 0 mild .. 1 freezing
    wet: float  # effective wetness of the pitch after drainage
    wind: float  # 0 calm .. 1 gale
    pitch_quality: float  # 1 perfect
    long_pass_penalty: float  # success lost by long balls, a probability offset
    first_touch_mult: float  # multiplier on first touch (<= 1)
    dribble_mult: float  # multiplier on dribbling (<= 1)
    injury_mult: float  # multiplier on injury hazard (>= 1)


NEUTRAL = Conditions(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0)


def conditions_for(weather: Weather, stadium: Stadium | None, cfg: WeatherConfig) -> Conditions:
    """Compute the match conditions (neutral when the weather is switched off)."""
    if not cfg.enabled:
        return NEUTRAL
    quality = stadium.pitch.quality if stadium is not None else cfg.pitch_default_quality
    drainage = stadium.pitch.drainage if stadium is not None else 0.5
    heat = clamp((weather.temperature_c - cfg.heat_start_c) / cfg.heat_span_c, 0.0, 1.0)
    cold = clamp((cfg.cold_end_c - weather.temperature_c) / cfg.cold_span_c, 0.0, 1.0)
    wet = clamp(weather.pitch_wetness * (1.0 - cfg.drainage_relief * drainage), 0.0, 1.0)
    wind = clamp(weather.wind_speed_mps / cfg.wind_scale_mps, 0.0, 1.0)
    poor_pitch = 1.0 - quality
    return Conditions(
        heat=heat,
        cold=cold,
        wet=wet,
        wind=wind,
        pitch_quality=quality,
        long_pass_penalty=cfg.wet_long_pass * wet
        + cfg.wind_long_pass * wind
        + cfg.poor_pitch_pass * poor_pitch,
        first_touch_mult=1.0 - cfg.wet_first_touch * wet - cfg.cold_first_touch * cold,
        dribble_mult=1.0 - cfg.wet_dribble * wet - cfg.poor_pitch_dribble * poor_pitch,
        injury_mult=(1.0 + cfg.injury_wet * wet)
        * (1.0 + cfg.injury_cold * cold)
        * (1.0 + cfg.poor_pitch_injury * poor_pitch),
    )


def apply_conditions(skills: Skills, conditions: Conditions) -> Skills:
    """Return the skills after weather and pitch: wet or cold ground hurts touch and dribbling."""
    if conditions is NEUTRAL:
        return skills
    return replace(
        skills,
        first_touch=skills.first_touch * conditions.first_touch_mult,
        dribbling=skills.dribbling * conditions.dribble_mult,
    )
