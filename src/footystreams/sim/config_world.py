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


class FatigueConfig(DomainModel):
    """In-match exhaustion: how fast it builds and what it does to skills (02 section 9)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "match_s": "S",
        "base_rate": "S",
        "carried_fatigue_weight": "S",
        "carried_fitness_weight": "S",
        "stamina_weight": "S",
        "fitness_weight": "S",
        "work_rate_weight": "S",
        "keeper_load": "S",
        "defence_load": "S",
        "midfield_load": "S",
        "attack_load": "S",
        "press_swing": "S",
        "tempo_swing": "S",
        "heat_weight": "S",
        "wet_weight": "S",
        "travel_weight": "S",
        "ten_men_load": "S",
        "altitude_scale_m": "S",
        "altitude_cap": "S",
        "halftime_recovery": "S",
        "max_exhaustion": "S",
        "physical_k": "S",
        "mental_k": "S",
        "mental_onset": "S",
        "technical_k": "S",
        "technical_onset": "S",
        "refresh_step": "S",
    }

    enabled: bool = False  # switched on in the commit that enables M6 behaviour
    match_s: float = 5400.0  # drain is expressed per full match
    base_rate: float = 0.60  # exhaustion gained over 90 minutes by an average, unhurried player
    carried_fatigue_weight: float = 0.6  # starting exhaustion = 0.6 fatigue + 0.4 (1 - fitness)
    carried_fitness_weight: float = 0.4
    stamina_weight: float = 0.5
    fitness_weight: float = 0.25
    work_rate_weight: float = 0.5
    keeper_load: float = 0.25  # a goalkeeper tires a quarter as fast
    defence_load: float = 0.9
    midfield_load: float = 1.1
    attack_load: float = 1.0
    press_swing: float = 0.4  # pressing intensity 0 -> x0.8, 1 -> x1.2
    tempo_swing: float = 0.3
    heat_weight: float = 0.5
    wet_weight: float = 0.25
    travel_weight: float = 0.04  # away sides in a hostile or distant ground tire a little faster
    ten_men_load: float = 0.10  # extra drain for a side a man down
    altitude_scale_m: float = 20_000.0  # metres of altitude that would add 100% drain
    altitude_cap: float = 0.15
    halftime_recovery: float = 0.06  # the only way exhaustion ever falls
    max_exhaustion: float = 1.5
    physical_k: float = 0.30  # physical skills x (1 - k x E^2)
    mental_k: float = 0.25  # mental skills x (1 - k x max(0, E - onset)^2)
    mental_onset: float = 0.4
    technical_k: float = 0.15
    technical_onset: float = 0.2
    refresh_step: float = 0.05  # skills are rebuilt when exhaustion crosses a multiple of this


class HomeAdvantageConfig(DomainModel):
    """The crowd channel of home advantage (docs/design/02 section 8; scaled by SimConfig)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "crowd_lift": "S",
        "away_pressure": "S",
        "default_capacity": "S",
        "default_axis": "S",
        "toxicity_share": "S",
        "big_match_share": "S",
    }

    enabled: bool = False  # switched on in the commit that enables M6 behaviour
    crowd_lift: float = 0.025  # share of mental attributes a full, loud crowd adds at home
    away_pressure: float = 0.02  # share of away composure a full, hostile crowd removes
    default_capacity: int = 40_000  # used when the home sheet carries no stadium
    default_axis: float = 0.5  # atmosphere, proximity, passion, weight when unknown
    toxicity_share: float = 0.5  # share of the away pressure that does not depend on toxicity
    big_match_share: float = 0.5  # share of the home lift that does not depend on big_match
