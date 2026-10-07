"""Environment knobs: weather and pitch, home advantage and fatigue (02 sections 8-10)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from footystreams.domain.base import DomainModel, UsageTag


class WeatherConfig(DomainModel):
    """How rain, heat, cold, wind and the pitch change play (docs/design/02 section 10)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "heat_start_c": "S",
        "heat_span_c": "S",
        "cold_end_c": "S",
        "cold_span_c": "S",
        "wet_long_pass": "S",
        "wind_long_pass": "S",
        "wind_scale_mps": "S",
        "wet_first_touch": "S",
        "cold_first_touch": "S",
        "wet_dribble": "S",
        "injury_wet": "S",
        "injury_cold": "S",
        "pitch_default_quality": "S",
        "drainage_relief": "S",
        "poor_pitch_pass": "S",
        "poor_pitch_dribble": "S",
        "poor_pitch_injury": "S",
    }

    enabled: bool = False  # switched on in the commit that enables M6 behaviour
    heat_start_c: float = 22.0  # heat builds from here...
    heat_span_c: float = 12.0  # ...to its maximum this many degrees higher
    cold_end_c: float = 6.0  # cold builds below here...
    cold_span_c: float = 12.0  # ...to its maximum this many degrees lower
    wet_long_pass: float = 0.04  # success lost by long balls on a soaked pitch
    wind_long_pass: float = 0.03  # success lost by long balls in a gale
    wind_scale_mps: float = 15.0  # wind speed that counts as a gale
    wet_first_touch: float = 0.03  # share of first touch lost on a soaked pitch
    cold_first_touch: float = 0.01
    wet_dribble: float = 0.04  # share of dribbling lost on a soaked pitch
    injury_wet: float = 0.15  # injury hazard added by a soaked pitch
    injury_cold: float = 0.10
    pitch_default_quality: float = 0.7  # used when the home sheet carries no stadium
    drainage_relief: float = 0.5  # share of wetness a perfect drainage system removes
    poor_pitch_pass: float = 0.02  # long-ball success lost on the worst possible pitch
    poor_pitch_dribble: float = 0.02
    poor_pitch_injury: float = 0.10
