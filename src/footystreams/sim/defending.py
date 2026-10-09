"""Defending off the ball: lane-cutting, cover and balance for the men who are not pressing.

The nearest defenders press the carrier (`movement.choose_pressers`). Everyone else has a job too,
so no defender stands on his slot while the ball is in play: one stands in the passing lane to
the most dangerous receivers (a cover shadow, so the presser's man cannot simply be found), one
covers behind the presser, the rest mark a man or, with nobody left to mark, shift across toward
the ball side to compress the space. Pure functions of the positions and the config: no draws.
"""

from __future__ import annotations

from footystreams.sim.config import PositionConfig
from footystreams.sim.geometry import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Point,
    squared_distance_m,
)
from footystreams.sim.movement import mark_spots, opponents_in_frame
from footystreams.sim.state import PlayerState, TeamState

Free = list[tuple[PlayerState, Point]]  # an unassigned defender and his slot target (team frame)
Assignments = dict[int, tuple[Point, float]]  # slot -> (spot to stand on, weight toward it)
_BEHIND_CARRIER = 0.05  # frame x beyond the carrier at which a receiver is a back pass


def _gap_squared(a: Point, b: Point) -> float:
    return squared_distance_m(a[0], a[1], b[0], b[1])


def lane_cutting_spots(
    free: Free, rivals: list[tuple[PlayerState, Point]], carrier: Point, cfg: PositionConfig
) -> dict[int, Point]:
    """Send up to `lane_cut_count` defenders to stand between the carrier and his best receivers.

    Receivers are ranked by how close they are to the carrier and how far up the pitch they stand
    (a ball played back is no danger); each takes the free defender nearest the shadow spot.
    """
    reach = cfg.lane_reach_m**2
    ranked = sorted(
        (_gap_squared(carrier, spot), rival.slot, spot)
        for rival, spot in rivals
        if spot[0] <= carrier[0] + _BEHIND_CARRIER
        and _gap_squared(carrier, spot) <= cfg.lane_range_m**2
    )
    spots: dict[int, Point] = {}
    for _, _, receiver in ranked[: cfg.lane_cut_count]:
        shadow = (
            carrier[0] + cfg.shadow_share * (receiver[0] - carrier[0]),
            carrier[1] + cfg.shadow_share * (receiver[1] - carrier[1]),
        )
        candidates = [
            (_gap_squared(target, shadow), player.slot)
            for player, target in free
            if player.slot not in spots
        ]
        if not candidates:
            break
        gap, slot = min(candidates)
        if gap <= reach:
            spots[slot] = shadow
    return spots


def cover_spot(close_in: Point, ball: Point, cfg: PositionConfig) -> Point:
    """Where the man covering the presser stands: behind him and toward the middle of the pitch."""
    toward_middle = 1.0 if ball[1] < 0.5 else -1.0  # noqa: PLR2004 - the centre line
    return (
        close_in[0] - cfg.cover_depth_m / PITCH_LENGTH_M,
        ball[1] + toward_middle * cfg.cover_width_m / PITCH_WIDTH_M,
    )


def balance_spot(slot: Point, ball: Point, cfg: PositionConfig) -> Point:
    """A free defender's place: his slot shifted across toward the ball side to close the space."""
    return slot[0], slot[1] + cfg.balance_pull * (ball[1] - slot[1])


def plan_defending(
    team: TeamState,
    opponents: TeamState,
    free: Free,
    ball_and_press: tuple[Point, Point],
    cfg: PositionConfig,
) -> Assignments:
    """Give every free defender a job: cut a lane, mark, cover the presser or balance the shape.

    `ball_and_press` is the ball and the spot the first presser closes in to (team frame).
    """
    ball, close_in = ball_and_press
    rivals = opponents_in_frame(team, opponents)
    plan: Assignments = {}
    for slot, spot in lane_cutting_spots(free, rivals, ball, cfg).items():
        plan[slot] = (spot, cfg.lane_cut_weight)
    rest = [(player, target) for player, target in free if player.slot not in plan]
    marked: set[int] = set()
    lines = {player.slot: player.line for player, _ in rest}
    for slot, spot in mark_spots(
        rivals, rest, cfg.marking_range_m, cfg.marking_goalside_m, marked
    ).items():
        plan[slot] = (spot, cfg.marking_weight[lines[slot]])
    rest = [(player, target) for player, target in rest if player.slot not in plan]
    if rest:
        coverer = min(rest, key=lambda entry: (_gap_squared(entry[1], close_in), entry[0].slot))
        plan[coverer[0].slot] = (cover_spot(close_in, ball, cfg), cfg.cover_weight)
        rest = [(player, target) for player, target in rest if player is not coverer[0]]
    for slot, spot in mark_spots(
        rivals, rest, cfg.free_marking_range_m, cfg.marking_goalside_m, marked
    ).items():
        plan[slot] = (spot, cfg.free_mark_weight)
    for player, target in rest:
        plan.setdefault(player.slot, (balance_spot(target, ball, cfg), 1.0))
    return plan
