"""Pressure on the ball carrier and openness of a pass target, from current positions.

`pressure` sums the three nearest opponents' closing-down effect (docs/design/02 section 4.2);
`openness` mixes the receiver's own space with how clear the passing lane is. Both are in [0, 1].
"""

from __future__ import annotations

from footystreams.sim.config import PressureConfig
from footystreams.sim.geometry import distance_m, segment_distance_m
from footystreams.sim.mathx import clamp
from footystreams.sim.state import PlayerState, TeamState

NEAREST_PRESSERS = 3
_PERCENT = 100.0
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


def pressure_on(carrier: PlayerState, opponents: TeamState, cfg: PressureConfig) -> float:
    """Return the pressure on the carrier in [0, 1] from the nearest opponents."""
    radius = cfg.radius_base_m + cfg.radius_range_m * opponents.view.press_intensity
    total = 0.0
    for gap, presser in nearest_opponents(opponents, carrier.x, carrier.y, NEAREST_PRESSERS):
        reach = max(0.0, 1.0 - gap / radius)
        total += reach * presser_intensity(presser, cfg)
    return clamp(total, 0.0, 1.0)


def openness(
    carrier: PlayerState,
    receiver_x: float,
    receiver_y: float,
    opponents: TeamState,
    cfg: PressureConfig,
) -> float:
    """Return how free a receiver is in [0, 1]: own space mixed with a clear passing lane."""
    space = 1e9
    lane = 1e9
    start = (carrier.x, carrier.y)
    end = (receiver_x, receiver_y)
    for player in opponents.players:
        space = min(space, distance_m(receiver_x, receiver_y, player.x, player.y))
        lane = min(lane, segment_distance_m((player.x, player.y), start, end))
    own_space = clamp(space / cfg.open_distance_m, 0.0, 1.0)
    clear_lane = clamp(lane / cfg.lane_clear_m, 0.0, 1.0)
    return cfg.open_weight * own_space + (1.0 - cfg.open_weight) * clear_lane
