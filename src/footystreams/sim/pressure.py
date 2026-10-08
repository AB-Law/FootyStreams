"""Pressure on the ball carrier and openness of a pass target, from current positions.

`pressure` sums the three nearest opponents' closing-down effect (docs/design/02 section 4.2);
`openness` mixes the receiver's own space with how clear the passing lane is. Both are in [0, 1].
"""

from __future__ import annotations

from math import sqrt

from footystreams.sim.config import PressureConfig
from footystreams.sim.geometry import PITCH_LENGTH_M, PITCH_WIDTH_M, distance_m
from footystreams.sim.mathx import clamp
from footystreams.sim.state import PlayerState, TeamState

NEAREST_PRESSERS = 3
_FAR_SQUARED = 1e12  # larger than any squared pitch distance
_ATTRIBUTE_PAIR_SCALE = 200.0  # work_rate + aggression, each on 1-100


def nearest_opponents(
    opponents: TeamState, x: float, y: float, count: int
) -> list[tuple[float, PlayerState]]:
    """Return the `count` opponents closest to a point as (distance_m, player), nearest first."""
    ranked = [
        (distance_m(x, y, player.x, player.y), player.slot, player) for player in opponents.players
    ]
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return [(gap, player) for gap, _, player in ranked[:count]]


def presser_intensity(player: PlayerState, cfg: PressureConfig) -> float:
    """Return how much pressure this defender brings when close (work rate and aggression)."""
    drive = (player.skills.work_rate + player.skills.aggression) / _ATTRIBUTE_PAIR_SCALE
    return cfg.presser_floor + (1.0 - cfg.presser_floor) * drive


def pressure_from(
    nearest: list[tuple[float, PlayerState]], opponents: TeamState, cfg: PressureConfig
) -> float:
    """Return the pressure in [0, 1] from already-ranked nearest opponents (nearest first)."""
    radius = cfg.radius_base_m + cfg.radius_range_m * opponents.view.press_intensity
    total = 0.0
    for gap, presser in nearest:
        reach = max(0.0, 1.0 - gap / radius)
        total += reach * presser_intensity(presser, cfg)
    return clamp(total, 0.0, 1.0)


def pressure_on(carrier: PlayerState, opponents: TeamState, cfg: PressureConfig) -> float:
    """Return the pressure on the carrier in [0, 1] from the nearest opponents."""
    nearest = nearest_opponents(opponents, carrier.x, carrier.y, NEAREST_PRESSERS)
    return pressure_from(nearest, opponents, cfg)


def openness(
    carrier: PlayerState,
    receiver_x: float,
    receiver_y: float,
    opponents: TeamState,
    cfg: PressureConfig,
) -> float:
    """Return how free a receiver is in [0, 1]: own space mixed with a clear passing lane."""
    # Perf: M4-match-sweep - openness ran for 6 candidates x 22 distances per moment and was 30% of
    # match time through call overhead; the arithmetic is inlined in metres, squared until the end.
    cx, cy = carrier.x * PITCH_LENGTH_M, carrier.y * PITCH_WIDTH_M
    rx, ry = receiver_x * PITCH_LENGTH_M, receiver_y * PITCH_WIDTH_M
    lane_x, lane_y = rx - cx, ry - cy
    lane_length_squared = lane_x * lane_x + lane_y * lane_y
    least_space = least_lane = _FAR_SQUARED
    for player in opponents.players:
        ox, oy = player.x * PITCH_LENGTH_M, player.y * PITCH_WIDTH_M
        space = (ox - rx) * (ox - rx) + (oy - ry) * (oy - ry)
        if space < least_space:  # noqa: PLR1730 - min() call overhead dominates here
            least_space = space
        along = (
            ((ox - cx) * lane_x + (oy - cy) * lane_y) / lane_length_squared
            if lane_length_squared
            else 0.0
        )
        along = 0.0 if along < 0.0 else 1.0 if along > 1.0 else along
        off_x, off_y = ox - (cx + along * lane_x), oy - (cy + along * lane_y)
        gap = off_x * off_x + off_y * off_y
        if gap < least_lane:  # noqa: PLR1730
            least_lane = gap
    own_space = clamp(sqrt(least_space) / cfg.open_distance_m, 0.0, 1.0)
    clear_lane = clamp(sqrt(least_lane) / cfg.lane_clear_m, 0.0, 1.0)
    return cfg.open_weight * own_space + (1.0 - cfg.open_weight) * clear_lane
