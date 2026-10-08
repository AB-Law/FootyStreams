"""Laws-of-the-game knobs: the referee, discipline and out-of-play restarts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.sim.config_types import NonNegative, Positive, Share


class RefereeConfig(DomainModel):
    """How a referee turns a contact into a called foul (docs/design/02 section 6)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "threshold_base": "S",
        "strictness_swing": "S",
        "call_scale": "S",
        "consistency_noise": "S",
        "home_bias_scale": "S",
        "crowd_capacity": "S",
        "box_leniency": "S",
        "penalty_swing": "S",
    }

    threshold_base: float = 0.55  # severity at which an average referee calls half of the contacts
    strictness_swing: NonNegative = 0.25  # a strict referee lowers the threshold by this much
    call_scale: Positive = 0.12  # width of the call probability's S-curve
    consistency_noise: NonNegative = 0.10  # threshold jitter of a fully inconsistent referee
    home_bias_scale: NonNegative = 0.15  # threshold shift per unit of home bias x crowd
    crowd_capacity: int = Field(ge=1, default=40_000)  # attendance that counts as a full crowd
    box_leniency: float = (
        0.0  # extra severity a contact in the box needs (box_caution does the work)
    )
    # A penalty-prone referee lowers the box threshold by up to this.
    penalty_swing: NonNegative = 0.15


class DisciplineConfig(DomainModel):
    """Fouls, advantage and the restart delays after them (docs/design/02 section 6)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "contact_base": "S",
        "aggression_weight": "S",
        "dirtiness_weight": "S",
        "tackling_weight": "S",
        "derby_factor": "S",
        "booked_caution": "S",
        "box_caution": "S",
        "severity_base": "S",
        "severity_spread": "S",
        "severity_aggression": "S",
        "severity_dirtiness": "S",
        "careless_max": "S",
        "reckless_max": "S",
        "advantage_scale": "S",
        "dogso_min_frame_x": "S",
        "dogso_max_defenders_ahead": "S",
        "free_kick_s": "S",
        "free_kick_spread_s": "S",
        "yellow_base": "S",
        "yellow_tendency_swing": "S",
        "yellow_strictness_swing": "S",
        "second_booking_margin": "S",
        "red_threshold": "S",
        "dogso_red_share": "S",
        "card_s": "S",
        "card_spread_s": "S",
        "min_players": "S",
    }

    # Chance a challenge involves foul-worthy contact, for an average man (0 switches fouls off).
    contact_base: NonNegative = 0.9
    aggression_weight: NonNegative = 0.8
    dirtiness_weight: NonNegative = 0.5
    tackling_weight: NonNegative = 0.5  # better tacklers foul less
    derby_factor: NonNegative = 1.2
    booked_caution: Share = 0.5  # a booked player challenges half as recklessly
    box_caution: NonNegative = 0.35  # defenders in their own box tackle far more carefully
    severity_base: float = 0.25
    severity_spread: NonNegative = 0.5
    severity_aggression: NonNegative = 0.25
    severity_dirtiness: NonNegative = 0.20
    careless_max: Share = 0.45
    reckless_max: Share = 0.78
    advantage_scale: NonNegative = (
        0.5  # advantage chance = scale x the referee's advantage tendency
    )
    dogso_min_frame_x: Share = 0.78  # fouled man must be this far up the pitch to be "through"
    # Defenders (keeper included) between the fouled man and the goal for it to count as denied.
    dogso_max_defenders_ahead: int = Field(ge=0, le=10, default=1)
    free_kick_s: NonNegative = 25.0
    free_kick_spread_s: NonNegative = 10.0
    yellow_base: float = 0.70  # severity above which an average referee books a foul
    yellow_tendency_swing: NonNegative = 0.20  # a card-happy referee books milder fouls
    yellow_strictness_swing: NonNegative = 0.10
    second_booking_margin: NonNegative = 0.04  # referees hesitate to send a booked player off
    red_threshold: Share = 0.90  # severity above which a foul is a straight red
    dogso_red_share: Share = 0.60  # share of denied goal-scoring chances punished with a red
    card_s: NonNegative = 30.0
    card_spread_s: NonNegative = 10.0
    min_players: int = Field(ge=1, le=11, default=7)  # a side is never reduced below this

    @model_validator(mode="after")
    def _severity_bands_are_ordered(self) -> Self:
        """Careless fouls are milder than reckless ones."""
        if self.careless_max > self.reckless_max:
            msg = "discipline.careless_max must not exceed discipline.reckless_max"
            raise ValueError(msg)
        return self


class RestartConfig(DomainModel):
    """Out-of-play restarts: throw-ins, goal kicks, corners and the aerial duel (02 section 6)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "throw_in_s": "S",
        "throw_in_spread_s": "S",
        "goal_kick_s": "S",
        "goal_kick_spread_s": "S",
        "corner_s": "S",
        "corner_spread_s": "S",
        "overhit_min_m": "S",
        "overhit_max_m": "S",
        "blocked_corner_share": "S",
        "parry_corner_share": "S",
        "clearance_out_share": "S",
        "cross_corner_share": "S",
        "clearance_behind_share": "S",
        "dribble_out_share": "S",
        "direct_range_m": "S",
        "direct_share": "S",
        "wall_factor": "S",
        "free_kick_cross_share": "S",
        "penalty_off_target": "S",
        "penalty_woodwork": "S",
        "penalty_skill_pivot": "S",
        "penalty_goal_given_frame": "S",
        "penalty_skill_swing": "S",
        "penalty_distance_m": "S",
        "corner_keeper_claim": "S",
        "corner_shot_share": "S",
        "corner_xg_base": "S",
        "corner_delivery_swing": "S",
    }

    enabled: bool = (
        True  # False switches off throw-ins, goal kicks, corners, penalties, free-kick shots
    )
    throw_in_s: NonNegative = 10.0
    throw_in_spread_s: NonNegative = 4.0
    goal_kick_s: NonNegative = 17.0
    goal_kick_spread_s: NonNegative = 5.0
    corner_s: NonNegative = 24.0
    corner_spread_s: NonNegative = 6.0
    overhit_min_m: NonNegative = 6.0  # how far past its target an overhit pass travels
    overhit_max_m: NonNegative = 20.0
    blocked_corner_share: Share = 0.5  # blocked shots deflected behind
    parry_corner_share: Share = 0.5  # parried shots tipped behind
    clearance_out_share: Share = 0.5  # clearances that go into touch
    cross_corner_share: Share = 0.5  # blocked crosses deflected behind
    clearance_behind_share: Share = 0.35  # of clearances out near the own goal, over the line
    dribble_out_share: Share = 0.60  # heavy touches that run out of play
    direct_range_m: Positive = 32.0  # farthest a direct free kick is shot from
    direct_share: Share = 0.50  # chance a kick in range is shot rather than played
    wall_factor: NonNegative = 0.45  # a wall and a set keeper cut the xG of an open-play shot
    free_kick_cross_share: Share = 0.5  # of kicks outside direct range in the attacking half
    penalty_off_target: Share = 0.08  # chance a penalty misses the frame
    penalty_woodwork: Share = 0.03
    penalty_skill_pivot: float = 55.0
    penalty_goal_given_frame: Share = 0.88  # chance an on-frame penalty beats an average keeper
    penalty_skill_swing: NonNegative = 0.003  # per point of taker-minus-keeper skill
    penalty_distance_m: Positive = 11.0
    corner_keeper_claim: Share = 0.18
    corner_shot_share: Share = 0.46  # times the attackers' aerial share
    corner_xg_base: Share = 0.10
    corner_delivery_swing: Share = 0.20  # a good delivery lifts the attackers' share by this much

    @model_validator(mode="after")
    def _overhit_range_is_ordered(self) -> Self:
        """An overhit pass travels between its minimum and maximum distance past the target."""
        if self.overhit_min_m > self.overhit_max_m:
            msg = "restarts.overhit_min_m must not exceed restarts.overhit_max_m"
            raise ValueError(msg)
        return self


class OffsideConfig(DomainModel):
    """Offside: the flag, and how closely attackers hug the line (docs/design/02 section 5.3)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "call_base": "S",
        "call_consistency": "S",
        "margin_min": "S",
        "margin_range": "S",
        "mistime_zone": "S",
        "mistime_base": "S",
    }

    enabled: bool = True  # False lets attackers stand anywhere and never flags a pass
    call_base: NonNegative = 0.88  # chance an offside pass is flagged, for a middling referee
    call_consistency: NonNegative = 0.10  # more of it for a consistent referee
    margin_min: NonNegative = 0.002  # frame-x distance a sharp mover keeps from the line
    margin_range: NonNegative = 0.015  # extra distance for a player with no off-ball movement
    mistime_zone: NonNegative = 0.03  # receivers this close to the line may have mistimed the run
    mistime_base: Share = 0.7  # chance a near-line receiver is judged offside (x timing flaw)


class StoppageConfig(DomainModel):
    """Added time: how much stoppage becomes announced minutes (docs/design/02 section 12)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "minutes_per_stoppage": "S",
        "generosity_base": "S",
        "generosity_swing": "S",
        "first_half_min": "S",
        "first_half_max": "S",
        "second_half_min": "S",
        "second_half_max": "S",
    }

    enabled: bool = True  # False plays exactly 45 minutes a half
    minutes_per_stoppage: NonNegative = 0.65  # share of stopped time that is added back
    generosity_base: NonNegative = 0.7  # a stingy referee adds 0.7x, a generous one 1.3x
    generosity_swing: NonNegative = 0.6
    first_half_min: int = Field(ge=0, default=1)
    first_half_max: int = Field(ge=0, default=8)
    second_half_min: int = Field(ge=0, default=2)
    second_half_max: int = Field(ge=0, default=10)

    @model_validator(mode="after")
    def _added_time_ranges_are_ordered(self) -> Self:
        """Each half's minimum added time must not exceed its maximum."""
        if self.first_half_min > self.first_half_max:
            msg = "stoppage.first_half_min must not exceed stoppage.first_half_max"
            raise ValueError(msg)
        if self.second_half_min > self.second_half_max:
            msg = "stoppage.second_half_min must not exceed stoppage.second_half_max"
            raise ValueError(msg)
        return self
