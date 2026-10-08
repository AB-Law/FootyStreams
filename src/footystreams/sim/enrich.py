"""Extra fields the simulator records on pass, dribble and shot events when context is on.

Pure functions of what the resolver already knows (start, intended end, xG): they draw no random
numbers and, with `SimConfig.context.enabled` off, return nothing (docs/design/03 section 3).
"""

from __future__ import annotations

from footystreams.events.derive.threat import frame_value, threat
from footystreams.sim.flight import shot_flight
from footystreams.sim.geometry import Point
from footystreams.sim.mathx import clamp
from footystreams.sim.options import Option
from footystreams.sim.play import Play
from footystreams.sim.state import PlayerState

PRECISION = 4


def _position(point: Point) -> dict[str, float]:
    # Perf: M7-context - a plain dict is validated once by the event model; a Pos was built twice.
    return {
        "x": round(clamp(point[0], 0.0, 1.0), PRECISION),
        "y": round(clamp(point[1], 0.0, 1.0), PRECISION),
    }


def pass_fields(play: Play, start: Point, option: Option) -> dict[str, object]:
    """Return end position, progressiveness and threat gain of a pass from `start`."""
    if not play.cfg.context.enabled:
        return {}
    direction = play.state.attackers.attack_dir
    start_x, start_y = frame_value(start[0], direction), frame_value(start[1], direction)
    end_x, end_y = frame_value(option.end[0], direction), frame_value(option.end[1], direction)
    return {
        "end_pos": _position(option.end),
        "progressive": end_x - start_x >= play.cfg.context.progressive_frame_x,
        "xt_gain": round(threat(end_x, end_y) - threat(start_x, start_y), PRECISION),
    }


def dribble_fields(play: Play, option: Option, *, kept_ball: bool) -> dict[str, object]:
    """Return where a successful dribble ended (nothing when the ball was lost)."""
    if not play.cfg.context.enabled or not kept_ball:
        return {}
    return {"end_pos": _position(option.end)}


def shot_fields(play: Play, xg: float, shooter: PlayerState, outcome: str) -> dict[str, object]:
    """Return whether a shot was a big chance and how it travelled (target, bend, pace, loft)."""
    if not play.cfg.context.enabled:
        return {}
    path = shot_flight(play, shooter, outcome)
    return {
        "big_chance": xg >= play.cfg.context.big_chance_xg,
        "target": _position(path.target),
        "curve": round(path.curve, PRECISION),
        "speed_mps": path.speed_mps,
        "loft": path.loft,
    }
