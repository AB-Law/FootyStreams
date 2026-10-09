"""Open-play knobs: passing, shooting, dribbling, decisions, tempo and challenges."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.sim.config_types import NonNegative, Positive, Share


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
        "openness_exponent": "S",
        "pressure_exponent": "S",
        "length_free_m": "S",
        "min_probability": "S",
        "max_probability": "S",
        "difficulty_floor": "S",
        "difficulty_peak": "S",
        "difficulty_span_m": "S",
        "long_pass_m": "S",
        "cross_min_frame_x": "S",
        "cross_wide_offset": "S",
        "through_min_gain": "S",
        "through_min_length_m": "S",
    }

    base_short: Share = 0.96
    base_long: Share = 0.80
    base_through: Share = 0.74
    base_cross: Share = 0.62
    base_back: Share = 0.9025
    length_penalty_per_m: float = 0.0055
    skill_swing: float = 0.12  # damped: skill gaps must not compound into lopsided matches
    skill_pivot: float = 55.0
    skill_scale: Positive = 25.0
    receiver_touch_weight: float = 0.04
    pressure_penalty: float = 0.60
    openness_penalty: float = 0.20
    # A moderately marked receiver costs little; only a really closed one does. Squaring the
    # closedness (exponent 2) keeps a clear pass near-certain and leaves the misses to pressure
    # on the passer and to receivers who are properly marked.
    openness_exponent: Positive = 2.0
    # Likewise pressure on the passer: a free man hardly misses (exponent 1.5), a hurried one does.
    pressure_exponent: Positive = 1.5
    length_free_m: float = 8.0  # a pass this short loses nothing to distance
    min_probability: Share = 0.02
    max_probability: Share = 0.985
    # Pressure and an unmarked receiver matter less on a short pass: a five-metre ball is rarely
    # lost whoever is closing in, a long one often is. The penalties are scaled from
    # `difficulty_floor` at no length to `difficulty_peak` at `difficulty_span_m` and beyond.
    difficulty_floor: Share = 0.5
    difficulty_peak: Positive = 1.8
    difficulty_span_m: Positive = 30.0
    long_pass_m: Positive = 32.0
    cross_min_frame_x: float = 0.62
    cross_wide_offset: float = 0.28
    through_min_gain: float = 0.15
    through_min_length_m: float = 15.0

    @model_validator(mode="after")
    def _probability_bounds_are_ordered(self) -> Self:
        """The probability floor must not exceed the ceiling."""
        if self.min_probability > self.max_probability:
            msg = "passing.min_probability must not exceed passing.max_probability"
            raise ValueError(msg)
        return self


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
        "off_target_min": "S",
        "off_target_max": "S",
        "woodwork_share": "S",
        "keeper_swing": "S",
        "max_goal_given_on_target": "S",
        "keeper_holds": "S",
        "rebound_attacker_share": "S",
    }

    range_m: Positive = 35.0
    xg_cap: Positive = 0.4101
    xg_half: Positive = 0.44  # geometry constant: larger means lower xG from every spot
    pressure_penalty: Share = 0.7
    finishing_floor: Positive = 0.40
    finishing_span: NonNegative = 0.52
    min_xg: Share = 0.055  # below this a chance is not worth taking: no 20 m punts
    long_range_m: Positive = 20.0  # beyond this the shooter's long_shots replaces finishing
    block_base: Share = 0.12  # share of shots a defender gets in the way of
    block_pressure: Share = 0.15  # extra blocked share at full pressure
    off_target_base: Share = 0.48
    off_target_skill_swing: Share = 0.12  # a better finisher misses the frame less
    off_target_min: Share = 0.05  # floor and ceiling of the off-target share after skill
    off_target_max: Share = 0.6
    woodwork_share: float = Field(ge=0.0, lt=1.0, default=0.03)
    keeper_swing: NonNegative = 0.5  # how much keeper quality bends the chance of a goal
    max_goal_given_on_target: Share = 0.95
    keeper_holds: Share = 0.62  # share of saves the keeper catches
    rebound_attacker_share: Share = 0.40  # share of loose balls an attacker reaches first

    @model_validator(mode="after")
    def _shares_leave_room_for_an_on_target_shot(self) -> Self:
        """Blocked + off-target must stay below 1, or no shot could ever be on target."""
        if self.off_target_min > self.off_target_max:
            msg = "shot.off_target_min must not exceed shot.off_target_max"
            raise ValueError(msg)
        if self.block_base + self.block_pressure + self.off_target_max >= 1.0:
            msg = "shot.block_base + block_pressure + off_target_max must stay below 1"
            raise ValueError(msg)
        return self


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

    base: Share = 0.3223
    swing: float = 0.12
    scale: Positive = 20.0
    pressure_penalty: float = 0.15
    min_probability: Share = 0.05
    max_probability: Share = 0.95
    distance_m: Positive = 8.2947  # how far a dribble carries the ball

    @model_validator(mode="after")
    def _probability_bounds_are_ordered(self) -> Self:
        """The probability floor must not exceed the ceiling."""
        if self.min_probability > self.max_probability:
            msg = "dribble.min_probability must not exceed dribble.max_probability"
            raise ValueError(msg)
        return self


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
        "box_frame_x": "S",
        "box_min_gain": "S",
        "box_recycle_penalty": "S",
        "advance_value": "S",
        "advance_span_m": "S",
        "retreat_cost": "S",
        "through_open_floor": "S",
        "through_open_bonus": "S",
        "ping_pong_penalty": "S",
        "return_pass_penalty": "S",
        "mentality_swing": "S",
        "urgency_swing": "S",
        "temperature_base": "S",
        "temperature_scale": "S",
        "temperature_pressure": "S",
        "weight_floor": "S",
        "min_utility_weight": "S",
    }

    candidates: int = Field(ge=1, le=10, default=4)
    progress_scale: float = 12.7166  # utility per unit of threat gained
    loss_cost_base: float = 0.15
    loss_cost_own_third: float = 0.55  # extra cost of losing the ball at the own goal line
    lead_frame_x: float = 0.012  # passes are aimed slightly ahead of the receiver
    min_pass_m: float = 4.0
    shot_scale: float = 15.0
    shoot_on_sight_swing: float = 0.8
    clear_pressure: float = 0.422
    clear_max_frame_x: float = 0.30
    clear_base: float = 0.9
    clear_slope: float = 1.5
    directness_bias: float = 0.0723
    cross_bias: float = 1.1
    dribble_bias: float = 0.5
    recycle_bias: float = 0.4  # extra appeal of a back pass per unit of pressure
    # Attackers in the box do not shuffle the ball sideways: a pass there that gains no threat, or
    # that hands the ball straight back to the man who gave it, loses utility, so a forward ball,
    # a dribble or a shot wins (M8 realism pass).
    box_frame_x: float = 0.82  # the final third from this frame x
    box_min_gain: float = 0.02  # threat a final-third pass must gain to count as going forward
    box_recycle_penalty: float = 1.0
    # Gaining ground is worth something in its own right: the threat map is nearly flat in the own
    # and middle thirds, so a pass sideways scored almost as well as one to a free man ahead and the
    # choice between them was a coin flip. A pass earns `advance_value` per `advance_span_m` gained
    # (up to one and a half spans) and pays `retreat_cost` per span given up, less the more the
    # passer is pressed.
    advance_value: float = 0.12
    advance_span_m: float = 25.0
    retreat_cost: float = 0.1
    # A runner in space is worth finding: a through ball or a long ball to a receiver who is more
    # open than `through_open_floor` gains `through_open_bonus` per unit of openness above it.
    through_open_floor: float = 0.55
    through_open_bonus: float = 3.0
    ping_pong_penalty: float = 1.5
    # Anywhere on the pitch, a pass straight back to the man who just gave the ball loses
    # `return_pass_penalty` times the square of the returns already played in a row plus one: a
    # one-two is fine, the third and fourth pass between the same two are not.
    return_pass_penalty: float = 0.3
    mentality_swing: float = 0.0116
    urgency_swing: float = 0.3
    temperature_base: Positive = 0.35
    temperature_scale: Positive = 1.4
    temperature_pressure: float = 0.4
    weight_floor: Positive = 0.02
    min_utility_weight: Positive = 0.2  # floor of the progress, keep and risk weights


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

    pass_base_s: Positive = 2.6
    pass_per_m_s: float = 0.06
    dribble_s: Positive = 3.6
    shot_s: Positive = 2.2
    clear_s: Positive = 2.8
    tackle_s: Positive = 1.6
    celebration_s: Positive = 55.0  # goal celebration and restart
    celebration_spread_s: NonNegative = 12.0
    noise: float = Field(ge=0.0, lt=1.0, default=0.3)  # +-30% on every duration
    tempo_swing: float = Field(
        ge=0.0, lt=1.0, default=0.3
    )  # tempo 0 -> x1.15 slower, tempo 1 -> x0.85 quicker


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

    attempt_rate: NonNegative = 0.14  # per moment, times the pressure on the carrier
    attempt_radius_m: Positive = 4.0
    tackle_base: Share = 0.45
    tackle_swing: float = 0.10
    tackle_scale: Positive = 20.0
    fail_intercept: Share = 0.42
    fail_loose: Share = 0.18  # the rest of failed passes go out of play
    fail_out_long_shift: Share = 0.15  # long balls and crosses are likelier to go out
    dribble_tackled_share: Share = 0.8
    clearance_teammate_share: Share = 0.42
    clearance_spread: float = 0.15

    @model_validator(mode="after")
    def _failed_pass_shares_fit(self) -> Self:
        """Intercepted + loose cannot exceed 1; the remainder goes out of play."""
        if self.fail_intercept + self.fail_loose > 1.0:
            msg = "challenge.fail_intercept + fail_loose must not exceed 1"
            raise ValueError(msg)
        return self
