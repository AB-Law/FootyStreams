"""Attacking support: team-mates near the ball carrier move to give him passing angles.

Triangles are attempted, not guaranteed. The nearest few team-mates each pick, from a fixed set
of angles round the carrier (a short square ball, an angled forward ball, a runner ahead, a
safety ball behind), the spot where he would be most free: far from every opponent and with the
passing lane clear of them. A spot a defender has cut off scores low, so the player drifts to the
next best; the further he has to run, the less a spot pays, which keeps him from jittering between
two of them. Pure functions of the positions and the config: no random draws.
"""

from __future__ import annotations

from math import sqrt

from footystreams.sim.config import PositionConfig
from footystreams.sim.geometry import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Point,
    squared_distance_m,
)
from footystreams.sim.mathx import PERCENT, clamp
from footystreams.sim.state import PlayerState

# Where a supporter can stand, in metres from the carrier: (ahead, across). Ahead is toward goal.
ANGLES: tuple[tuple[float, float], ...] = (
    (10.0, -9.0),
    (10.0, 9.0),
    (18.0, 0.0),
    (0.0, -12.0),
    (0.0, 12.0),
    (-8.0, -8.0),
    (-8.0, 8.0),
)
_FAR_SQUARED = 1e12  # larger than any squared pitch distance
_FORWARD_BONUS = 0.15  # a spot ahead of the ball is worth a little more than one behind it


def _spot(carrier: Point, angle: tuple[float, float]) -> Point:
    return (
        clamp(carrier[0] + angle[0] / PITCH_LENGTH_M, 0.0, 1.0),
        clamp(carrier[1] + angle[1] / PITCH_WIDTH_M, 0.0, 1.0),
    )


def _freedom(carrier: Point, spot: Point, rivals: list[Point], cfg: PositionConfig) -> float:
    """How open a spot is in [0, 1]: space round it mixed with a clear lane from the carrier."""
    # Perf: M8-sim-profile - run per angle per position step; plain comparisons and inlined
    # metres beat min() and distance calls here.
    cx, cy = carrier[0] * PITCH_LENGTH_M, carrier[1] * PITCH_WIDTH_M
    sx, sy = spot[0] * PITCH_LENGTH_M, spot[1] * PITCH_WIDTH_M
    lane_x, lane_y = sx - cx, sy - cy
    length_squared = lane_x * lane_x + lane_y * lane_y
    least_space = least_lane = _FAR_SQUARED
    for rival in rivals:
        rx, ry = rival[0] * PITCH_LENGTH_M, rival[1] * PITCH_WIDTH_M
        space = (rx - sx) * (rx - sx) + (ry - sy) * (ry - sy)
        if space < least_space:  # noqa: PLR1730 - min() call overhead dominates here
            least_space = space
        along = (
            ((rx - cx) * lane_x + (ry - cy) * lane_y) / length_squared if length_squared else 0.0
        )
        along = 0.0 if along < 0.0 else 1.0 if along > 1.0 else along
        off_x, off_y = rx - (cx + along * lane_x), ry - (cy + along * lane_y)
        miss = off_x * off_x + off_y * off_y
        if miss < least_lane:  # noqa: PLR1730
            least_lane = miss
    open_space = clamp(sqrt(least_space) / cfg.spacing_m, 0.0, 1.0)
    clear_lane = clamp(sqrt(least_lane) / cfg.support_lane_m, 0.0, 1.0)
    return cfg.support_space_share * open_space + (1.0 - cfg.support_space_share) * clear_lane


def support_spots(
    movers: list[tuple[PlayerState, Point]],
    carrier: Point,
    rivals: list[Point],
    cfg: PositionConfig,
) -> dict[int, Point]:
    """Return the angle each of the nearest team-mates takes (slot -> spot, team frame).

    `movers` are the outfield team-mates as (player, current position in the team's frame);
    greedy in order of distance from the carrier, each takes the best angle nobody has taken.
    """
    near = sorted(
        (squared_distance_m(*carrier, *at), player.slot, player, at)
        for player, at in movers
        if squared_distance_m(*carrier, *at) <= cfg.support_range_m**2
    )
    # Perf: M8-sim-profile - how open an angle is does not depend on who takes it, so it is scored
    # once per angle, not once per player and angle (it was 28% of a match).
    worth = {}
    for angle in ANGLES:
        spot = _spot(carrier, angle)
        worth[spot] = _freedom(carrier, spot, rivals, cfg) + (
            _FORWARD_BONUS if spot[0] > carrier[0] else 0.0
        )
    claimed: dict[int, Point] = {}
    for _, _, player, at in near[: cfg.support_count]:
        if not worth:
            break
        best = max(
            worth,
            key=lambda spot: (
                worth[spot]
                - sqrt(squared_distance_m(at[0], at[1], spot[0], spot[1])) / cfg.support_travel_m,
                -spot[0],
                spot[1],
            ),
        )
        del worth[best]
        claimed[player.slot] = best
    return claimed


def support_weight(player: PlayerState, cfg: PositionConfig) -> float:
    """How far a supporter leaves his slot: sharper off-the-ball movers commit more."""
    return clamp(cfg.support_weight * (0.5 + player.skills.off_ball_movement / PERCENT), 0.0, 1.0)
