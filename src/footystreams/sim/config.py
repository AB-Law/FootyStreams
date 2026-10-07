"""SimConfig: every tunable of the simulation, frozen, hashable and mergeable.

One group per concern (docs/design/02 section 14.6); groups are added by the milestone that
introduces the behaviour. `config_hash` identifies the exact numbers a match was played with.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.canonical import canonical_json

CONFIG_HASH_LENGTH = 16


class PositionConfig(DomainModel):
    """How the 22 players drift around their formation slots (docs/design/02 section 4)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "push_in_possession": "S",
        "drop_out_of_possession": "S",
        "line_range": "S",
        "pull_x": "S",
        "pull_y": "S",
        "width_min": "S",
        "width_max": "S",
        "base_speed_mps": "S",
        "speed_range_mps": "S",
    }

    push_in_possession: float = 0.09
    drop_out_of_possession: float = 0.07
    line_range: float = 0.20  # x shift of the defensive line between line_height 0 and 1
    pull_x: tuple[float, float, float, float] = (0.10, 0.28, 0.40, 0.35)  # GK, DEF, MID, ATT
    pull_y: float = 0.22
    width_min: float = 0.80
    width_max: float = 1.25
    base_speed_mps: float = 4.5
    speed_range_mps: float = 3.5


class PressureConfig(DomainModel):
    """Pressure on the carrier and openness of a pass target (docs/design/02 section 4.2)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "radius_base_m": "S",
        "radius_range_m": "S",
        "presser_floor": "S",
        "open_distance_m": "S",
        "lane_clear_m": "S",
        "open_weight": "S",
    }

    radius_base_m: float = 3.0
    radius_range_m: float = 8.0  # extra radius at full pressing intensity
    presser_floor: float = 0.4  # share of a presser's pressure that every defender brings
    open_distance_m: float = 8.0  # distance to the nearest opponent that counts as fully open
    lane_clear_m: float = 4.0  # defender distance to the passing lane that counts as clear
    open_weight: float = 0.55  # share of openness from the receiver's own space vs the lane


class PassConfig(DomainModel):
    """Pass classification and success model (docs/design/02 section 5.3)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "base_short": "S",
        "base_long": "S",
        "base_through": "S",
        "base_cross": "S",
        "base_back": "S",
        "length_penalty_per_m": "S",
        "skill_swing": "S",
        "skill_pivot": "S",
        "skill_scale": "S",
        "receiver_touch_weight": "S",
        "pressure_penalty": "S",
        "openness_penalty": "S",
        "min_probability": "S",
        "max_probability": "S",
        "long_pass_m": "S",
        "cross_min_frame_x": "S",
        "cross_wide_offset": "S",
        "through_min_gain": "S",
        "through_min_length_m": "S",
    }

    base_short: float = 0.98
    base_long: float = 0.80
    base_through: float = 0.74
    base_cross: float = 0.62
    base_back: float = 1.0
    length_penalty_per_m: float = 0.0035
    skill_swing: float = 0.5
    skill_pivot: float = 55.0
    skill_scale: float = 25.0
    receiver_touch_weight: float = 0.10
    pressure_penalty: float = 0.30
    openness_penalty: float = 0.20
    min_probability: float = 0.02
    max_probability: float = 0.985
    long_pass_m: float = 32.0
    cross_min_frame_x: float = 0.62
    cross_wide_offset: float = 0.28
    through_min_gain: float = 0.15
    through_min_length_m: float = 15.0


class ShotConfig(DomainModel):
    """Shot quality (xG) model (docs/design/02 section 5.3)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "range_m": "S",
        "xg_cap": "S",
        "xg_half": "S",
        "pressure_penalty": "S",
        "finishing_floor": "S",
        "finishing_span": "S",
        "min_xg": "S",
        "long_range_m": "S",
    }

    range_m: float = 35.0
    xg_cap: float = 0.75
    xg_half: float = 0.44  # geometry constant: larger means lower xG from every spot
    pressure_penalty: float = 0.5
    finishing_floor: float = 0.80
    finishing_span: float = 0.40
    min_xg: float = 0.02
    long_range_m: float = 20.0  # beyond this the shooter's long_shots replaces finishing


class DribbleConfig(DomainModel):
    """Dribble success model."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "base": "S",
        "swing": "S",
        "scale": "S",
        "pressure_penalty": "S",
        "min_probability": "S",
        "max_probability": "S",
        "distance_m": "S",
    }

    base: float = 0.55
    swing: float = 0.45
    scale: float = 20.0
    pressure_penalty: float = 0.15
    min_probability: float = 0.05
    max_probability: float = 0.95
    distance_m: float = 8.0  # how far a dribble carries the ball


class DecisionConfig(DomainModel):
    """Utility weights and choice temperature of the carrier's decision (02 section 5.2)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "candidates": "S",
        "progress_scale": "S",
        "loss_cost_base": "S",
        "loss_cost_own_third": "S",
        "lead_frame_x": "S",
        "min_pass_m": "S",
        "shot_scale": "S",
        "shoot_on_sight_swing": "S",
        "clear_pressure": "S",
        "clear_max_frame_x": "S",
        "clear_base": "S",
        "clear_slope": "S",
        "directness_bias": "S",
        "cross_bias": "S",
        "dribble_bias": "S",
        "recycle_bias": "S",
        "mentality_swing": "S",
        "urgency_swing": "S",
        "temperature_base": "S",
        "temperature_scale": "S",
        "temperature_pressure": "S",
        "weight_floor": "S",
    }

    candidates: int = Field(ge=1, le=10, default=5)
    progress_scale: float = 10.0  # utility per unit of threat gained
    loss_cost_base: float = 0.15
    loss_cost_own_third: float = 0.55  # extra cost of losing the ball at the own goal line
    lead_frame_x: float = 0.012  # passes are aimed slightly ahead of the receiver
    min_pass_m: float = 4.0
    shot_scale: float = 7.0
    shoot_on_sight_swing: float = 0.8
    clear_pressure: float = 0.45
    clear_max_frame_x: float = 0.30
    clear_base: float = 0.9
    clear_slope: float = 1.5
    directness_bias: float = 0.6
    cross_bias: float = 0.6
    dribble_bias: float = 0.5
    recycle_bias: float = 0.4  # extra appeal of a back pass per unit of pressure
    mentality_swing: float = 0.5
    urgency_swing: float = 0.3
    temperature_base: float = 0.35
    temperature_scale: float = 2.0
    temperature_pressure: float = 0.4
    weight_floor: float = 0.02


class SimConfig(DomainModel):
    """Top-level simulation configuration (defaults are the shipped balance)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "model_profile": "S",
        "emit_frames": "S",
        "frame_interval_s": "S",
        "home_advantage_scale": "S",
        "positioning": "S",
        "pressure": "S",
        "passing": "S",
        "shot": "S",
        "dribble": "S",
        "decision": "S",
    }

    model_profile: str = "v1"
    emit_frames: bool = False
    frame_interval_s: int = Field(ge=1, le=60, default=1)
    home_advantage_scale: float = Field(ge=0.0, le=3.0, default=1.0)
    positioning: PositionConfig = Field(default_factory=PositionConfig)
    pressure: PressureConfig = Field(default_factory=PressureConfig)
    passing: PassConfig = Field(default_factory=PassConfig)
    shot: ShotConfig = Field(default_factory=ShotConfig)
    dribble: DribbleConfig = Field(default_factory=DribbleConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)


def config_hash(config: SimConfig) -> str:
    """Return a short stable hash of the full configuration (recorded on every match)."""
    text = canonical_json(config.model_dump(mode="json"))
    return hashlib.sha256(text.encode()).hexdigest()[:CONFIG_HASH_LENGTH]


def merge_config(base: SimConfig, overrides: Mapping[str, Any]) -> SimConfig:
    """Return `base` with a partial, possibly nested, mapping of overrides applied and validated."""
    merged = _deep_merge(base.model_dump(mode="python"), overrides)
    return SimConfig.model_validate(merged)


def _deep_merge(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overrides.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = value
    return result
