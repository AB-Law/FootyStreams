"""Movement knobs: where the 22 players stand and how pressure is felt (docs/design/02 s4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.sim.config_types import NonNegative, Positive, Share


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
        "wander_m": "S",
        "wander_period_s": "S",
        "press_count": "S",
        "press_speed_bonus": "S",
        "press_gap_m": "S",
        "cover_depth_m": "S",
        "cover_width_m": "S",
        "marking_weight": "S",
        "marking_goalside_m": "S",
        "marking_range_m": "S",
        "edge_margin": "S",
        "press_range_m": "S",
        "spacing_m": "S",
        "carrier_space_m": "S",
        "spacing_push": "S",
        "lane_cut_count": "S",
        "lane_range_m": "S",
        "lane_reach_m": "S",
        "shadow_share": "S",
        "lane_cut_weight": "S",
        "cover_weight": "S",
        "free_marking_range_m": "S",
        "free_mark_weight": "S",
        "balance_pull": "S",
        "support_count": "S",
        "support_range_m": "S",
        "support_weight": "S",
        "support_travel_m": "S",
        "support_lane_m": "S",
        "support_space_share": "S",
    }

    push_in_possession: NonNegative = 0.09
    drop_out_of_possession: NonNegative = 0.07
    line_range: NonNegative = 0.0225  # x shift of the defensive line between line_height 0 and 1
    pull_x: tuple[float, float, float, float] = (0.10, 0.28, 0.40, 0.35)  # GK, DEF, MID, ATT
    pull_y: Share = 0.22
    width_min: Positive = 0.80
    width_max: Positive = 1.25
    base_speed_mps: Positive = 4.5
    speed_range_mps: NonNegative = 3.5
    step_s: Positive = 2.0  # positions are refreshed once this much match time has passed
    # Off-ball life (M8 realism pass): nobody stands still, the nearest defenders close the ball
    # down and the rest pick up a man instead of holding a slot (docs/design/02 section 4).
    wander_m: tuple[float, float, float, float] = (0.0, 1.5, 3.0, 4.0)  # loop radius: GK, DEF...ATT
    wander_period_s: Positive = 11.0  # seconds one loop around the slot takes
    press_count: Positive = 1.5  # defenders who close the ball down at average press intensity
    press_speed_bonus: Positive = 1.3  # a presser sprints at this multiple of his pace
    press_gap_m: Positive = 3.0  # a presser closes to this far goal-side of the carrier
    cover_depth_m: Positive = (
        7.0  # each further presser covers this much deeper than the one before
    )
    cover_width_m: Positive = 3.5  # and this much wider, so they stand side by side, not in a heap
    marking_weight: tuple[float, float, float, float] = (0.0, 0.4, 0.3, 0.0)  # GK, DEF, MID, ATT
    marking_goalside_m: NonNegative = 3.5  # a marker stands this far goal-side of his man
    marking_range_m: Positive = 22.0  # a man further than this from the marker's slot is not marked
    edge_margin: Share = 0.035  # nobody is sent closer than this to a touchline (fraction of width)
    press_range_m: Positive = (
        28.0  # only players this close to the ball press it (the nearest always)
    )
    # Room to play: team-mates do not crowd each other or the man on the ball.
    spacing_m: Positive = 8.0  # a player aims away from a team-mate closer than this to his target
    carrier_space_m: Positive = 7.0  # and from the ball carrier, who needs space to play
    spacing_push: Share = 0.9  # how much of the overlap he gives up (1 moves him out entirely)
    # Defending off the ball: every defender who is not pressing has a job (sim/defending.py).
    lane_cut_count: Annotated[int, Field(ge=0)] = 1  # receivers whose passing lane a defender cuts
    lane_range_m: Positive = 25.0  # only receivers this close to the carrier are worth cutting off
    lane_reach_m: Positive = 22.0  # a cutter comes from at most this far from the lane
    shadow_share: Share = 0.6  # where on the lane he stands, from the carrier (1 = on the receiver)
    lane_cut_weight: Share = 0.5  # how far he leaves his slot for the shadow spot
    cover_weight: Share = 0.4  # the same for the man covering behind the presser
    free_marking_range_m: Positive = 40.0  # a defender with nobody near picks up a man this far off
    free_mark_weight: Share = 0.3
    balance_pull: Share = 0.3  # a free defender's shift across toward the ball side
    # Attacking support: team-mates near the carrier move to make angles (sim/support.py).
    support_count: Annotated[int, Field(ge=0)] = 3  # team-mates who offer themselves at a time
    support_range_m: Positive = 32.0  # only team-mates this close to the carrier are asked
    support_weight: Share = 0.65  # how far a supporter leaves his slot for his angle
    support_travel_m: Positive = (
        18.0  # the distance he will cross for an angle before it stops paying
    )
    support_lane_m: Positive = 4.0  # a defender this far from the passing lane leaves it clear
    support_space_share: Share = 0.5  # share of an angle's worth from room round it vs a clear lane


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

    radius_base_m: Positive = 3.0
    radius_range_m: NonNegative = 0.61  # extra radius at full pressing intensity
    presser_floor: Share = 0.4  # share of a presser's pressure that every defender brings
    open_distance_m: Positive = 8.0  # distance to the nearest opponent that counts as fully open
    lane_clear_m: Positive = 4.0  # defender distance to the passing lane that counts as clear
    open_weight: Share = 0.55  # share of openness from the receiver's own space vs the lane
