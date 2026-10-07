"""The offside rule as pure functions: the line, the position test and the flag probability."""

from __future__ import annotations

from footystreams.sim.config_rules import OffsideConfig
from footystreams.sim.geometry import frame_coordinate
from footystreams.sim.state import TeamState


def offside_line(defenders: TeamState, attack_dir: int) -> float:
    """Return the second-last defender's x in the attackers' frame (1.0 is their goal line)."""
    positions = sorted((frame_coordinate(p.x, attack_dir) for p in defenders.players), reverse=True)
    return positions[1] if len(positions) > 1 else positions[0]


def in_offside_position(receiver_fx: float, ball_fx: float, line: float) -> bool:
    """True when the receiver is beyond the line and ahead of the ball (frame x)."""
    return receiver_fx > line and receiver_fx > ball_fx


def call_probability(consistency: float, cfg: OffsideConfig) -> float:
    """Return the chance the referee flags an offside pass: 0.88 + 0.10 x consistency."""
    return cfg.call_base + cfg.call_consistency * consistency
