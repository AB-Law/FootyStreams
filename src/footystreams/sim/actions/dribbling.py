"""Dribble success probability against the nearest defender (02 section 5.3)."""

from __future__ import annotations

from footystreams.sim.config import DribbleConfig
from footystreams.sim.effective import Skills
from footystreams.sim.mathx import clamp, squash

_DRIBBLER_MIX = (0.60, 0.15, 0.15, 0.10)  # dribbling, agility, balance, flair
_DEFENDER_MIX = (0.50, 0.25, 0.25)  # tackling, anticipation, positioning


def dribbling_rating(player: Skills) -> float:
    """Blend of the attributes that carry the ball past a man (1-100 scale)."""
    a, b, c, d = _DRIBBLER_MIX
    return a * player.dribbling + b * player.agility + c * player.balance + d * player.flair


def defending_rating(player: Skills) -> float:
    """Blend of the attributes that stop a dribbler (1-100 scale)."""
    a, b, c = _DEFENDER_MIX
    return a * player.tackling + b * player.anticipation + c * player.positioning


def dribble_success_probability(
    dribbler: Skills, defender: Skills | None, pressure: float, cfg: DribbleConfig
) -> float:
    """Return the chance the carrier beats the nearest defender (or runs on if there is none)."""
    if defender is None:
        return cfg.max_probability
    edge = (dribbling_rating(dribbler) - defending_rating(defender)) / cfg.scale
    probability = (
        cfg.base + cfg.swing * (squash(edge) - 0.5) * 2.0 - cfg.pressure_penalty * pressure
    )
    return clamp(probability, cfg.min_probability, cfg.max_probability)
