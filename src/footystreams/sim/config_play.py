"""Open-play knobs: positioning, pressure, passing, shooting, dribbling, decisions, tempo."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag


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
        "step_s": "S",
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
    step_s: float = 4.0  # positions are refreshed once this much match time has passed


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
    skill_swing: float = 0.12  # damped: skill gaps must not compound into lopsided matches
    skill_pivot: float = 55.0
    skill_scale: float = 25.0
    receiver_touch_weight: float = 0.04
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
        "block_base": "S",
        "block_pressure": "S",
        "off_target_base": "S",
        "off_target_skill_swing": "S",
        "woodwork_share": "S",
        "keeper_swing": "S",
        "max_goal_given_on_target": "S",
        "keeper_holds": "S",
        "rebound_attacker_share": "S",
    }

    range_m: float = 35.0
    xg_cap: float = 0.40
    xg_half: float = 0.44  # geometry constant: larger means lower xG from every spot
    pressure_penalty: float = 0.7
    finishing_floor: float = 0.80
    finishing_span: float = 0.40
    min_xg: float = 0.02
    long_range_m: float = 20.0  # beyond this the shooter's long_shots replaces finishing
    block_base: float = 0.12  # share of shots a defender gets in the way of
    block_pressure: float = 0.15  # extra blocked share at full pressure
    off_target_base: float = 0.43
    off_target_skill_swing: float = 0.12  # a better finisher misses the frame less
    woodwork_share: float = 0.03
    keeper_swing: float = 0.5  # how much keeper quality bends the chance of a goal
    max_goal_given_on_target: float = 0.95
    keeper_holds: float = 0.62  # share of saves the keeper catches
    rebound_attacker_share: float = 0.40  # share of loose balls an attacker reaches first


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
    swing: float = 0.12
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

    candidates: int = Field(ge=1, le=10, default=4)
    progress_scale: float = 12.0  # utility per unit of threat gained
    loss_cost_base: float = 0.15
    loss_cost_own_third: float = 0.55  # extra cost of losing the ball at the own goal line
    lead_frame_x: float = 0.012  # passes are aimed slightly ahead of the receiver
    min_pass_m: float = 4.0
    shot_scale: float = 16.0
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


class TempoConfig(DomainModel):
    """How long each action takes, in seconds (docs/design/02 section 5.4)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "pass_base_s": "S",
        "pass_per_m_s": "S",
        "dribble_s": "S",
        "shot_s": "S",
        "clear_s": "S",
        "tackle_s": "S",
        "celebration_s": "S",
        "celebration_spread_s": "S",
        "noise": "S",
        "tempo_swing": "S",
    }

    pass_base_s: float = 2.6
    pass_per_m_s: float = 0.06
    dribble_s: float = 3.6
    shot_s: float = 2.2
    clear_s: float = 2.8
    tackle_s: float = 1.6
    celebration_s: float = 55.0  # goal celebration and restart
    celebration_spread_s: float = 12.0
    noise: float = 0.3  # +-30% on every duration
    tempo_swing: float = 0.3  # tempo 0 -> x1.15 slower, tempo 1 -> x0.85 quicker


class ChallengeConfig(DomainModel):
    """Tackles and what happens when a pass or dribble fails (02 sections 5.3, 5.5)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "attempt_rate": "S",
        "attempt_radius_m": "S",
        "tackle_base": "S",
        "tackle_swing": "S",
        "tackle_scale": "S",
        "fail_intercept": "S",
        "fail_loose": "S",
        "fail_out_long_shift": "S",
        "dribble_tackled_share": "S",
        "clearance_teammate_share": "S",
        "clearance_spread": "S",
    }

    attempt_rate: float = 0.10  # per moment, times the pressure on the carrier
    attempt_radius_m: float = 3.0
    tackle_base: float = 0.45
    tackle_swing: float = 0.10
    tackle_scale: float = 20.0
    fail_intercept: float = 0.55
    fail_loose: float = 0.20  # the rest of failed passes go out of play
    fail_out_long_shift: float = 0.15  # long balls and crosses are likelier to go out
    dribble_tackled_share: float = 0.8
    clearance_teammate_share: float = 0.42
    clearance_spread: float = 0.15
