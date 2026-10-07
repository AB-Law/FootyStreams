"""Shot quality: expected goals from geometry, pressure and the shooter (02 section 5.3)."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.sim.config import ShotConfig
from footystreams.sim.effective import Skills
from footystreams.sim.geometry import GOAL_WIDTH_M, PITCH_LENGTH_M, goal_distance_m
from footystreams.sim.mathx import clamp

_PERCENT = 100.0
_COMPOSURE_SHIELD = 150.0  # composure/150: even a perfectly composed shooter feels some pressure


@dataclass(frozen=True, slots=True)
class ShotChance:
    """The quality of one shot chance."""

    distance_m: float
    geometry_xg: float  # from position alone, before pressure and shooter
    xg: float  # after pressure and the shooter's finishing


def geometry_xg(frame_x: float, frame_y: float, cfg: ShotConfig) -> float:
    """Return the expected goals of an unpressured average shot from a frame point.

    The visible goal mouth is `7.32 m x (distance along the pitch / distance to goal)`; the
    relative size `u = mouth / distance` is mapped through `cap * u^3 / (u^3 + half)`, which gives
    about 0.6 from 6 m, 0.3 from 11 m, 0.10 from 18 m and 0.02 from 30 m straight on.
    """
    distance = goal_distance_m(frame_x, frame_y)
    if distance <= 0.0:
        return cfg.xg_cap
    along = (1.0 - frame_x) * PITCH_LENGTH_M
    mouth = GOAL_WIDTH_M * along / distance
    relative = mouth / distance
    cubed = relative * relative * relative
    return cfg.xg_cap * cubed / (cubed + cfg.xg_half)


def finishing_skill(shooter: Skills, distance_m: float, cfg: ShotConfig) -> float:
    """Return the attribute that decides the shot: long shots from range, finishing otherwise."""
    return shooter.long_shots if distance_m > cfg.long_range_m else shooter.finishing


def shot_chance(
    frame_point: tuple[float, float], shooter: Skills, pressure: float, cfg: ShotConfig
) -> ShotChance:
    """Return the quality of a shot from a frame point with the given pressure on the shooter."""
    frame_x, frame_y = frame_point
    distance = goal_distance_m(frame_x, frame_y)
    base = geometry_xg(frame_x, frame_y, cfg)
    pressure_factor = 1.0 - cfg.pressure_penalty * pressure * (
        1.0 - shooter.composure / _COMPOSURE_SHIELD
    )
    skill = finishing_skill(shooter, distance, cfg)
    skill_factor = cfg.finishing_floor + cfg.finishing_span * skill / _PERCENT
    return ShotChance(distance, base, clamp(base * pressure_factor * skill_factor, 0.0, 1.0))
