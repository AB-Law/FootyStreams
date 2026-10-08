"""Free kicks: the taker, then a direct shot, a cross into the box, or a short pass.

A direct kick inside shooting range is shot with the xG of an open-play chance cut by a wall
factor and scaled by the taker's dead-ball skill; farther out in the attacking half it is often
crossed (the corner's aerial duel); otherwise the taker simply plays on as the carrier
(docs/design/02 section 6).
"""

from __future__ import annotations

from typing import Literal

from footystreams.events.restarts import FreeKickEvent
from footystreams.sim.actions.corner import deliver
from footystreams.sim.actions.resolve_shot import resolve_shot
from footystreams.sim.actions.setpieces import choose_free_kick_taker, restart_delay
from footystreams.sim.actions.shooting import geometry_xg
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import Point, frame_coordinate, goal_distance_m
from footystreams.sim.mathx import PERCENT
from footystreams.sim.options import ActionKind, Option
from footystreams.sim.play import Play, actor, take_possession
from footystreams.sim.side import Side
from footystreams.sim.state import PlayerState

FreeKickKind = Literal["direct", "indirect"]
_ATTACKING_HALF = 0.6  # frame x beyond which a long free kick is crossed
_DEAD_BALL_MIX = (0.6, 0.4)  # set piece delivery, long shots
_KICK_PRESSURE = 0.3


def dead_ball_skill(taker: PlayerState) -> float:
    """Blend of the attributes that decide a shot from a free kick (1-100 scale)."""
    delivery, shooting = _DEAD_BALL_MIX
    return delivery * taker.skills.set_piece_delivery + shooting * taker.skills.long_shots


def free_kick_xg(play: Play, taker: PlayerState, frame_point: Point) -> float:
    """Return the quality of a direct kick: geometry x wall factor x dead-ball skill factor."""
    wall = play.cfg.restarts.wall_factor
    skill = 0.8 + 0.4 * dead_ball_skill(taker) / PERCENT
    return geometry_xg(frame_point[0], frame_point[1], play.cfg.shot) * wall * skill


def _shoot(play: Play, taker: PlayerState, frame_point: Point) -> float:
    state = play.state
    direction = state.team(taker.side).attack_dir
    goal = (frame_coordinate(1.0, direction), frame_coordinate(0.5, direction))
    xg = free_kick_xg(play, taker, frame_point)
    state.assist_from = None
    option = Option(ActionKind.SHOOT, 0.0, xg, goal, _KICK_PRESSURE, xg=xg)
    return resolve_shot(play, option)


def take_free_kick(
    play: Play, side: Side, spot: Point, kind: FreeKickKind, caused_by: str | None
) -> float:
    """Restart play with a free kick for `side` at `spot`; return the stoppage in seconds."""
    state, cfg = play.state, play.cfg
    taker = choose_free_kick_taker(state.team(side))
    meta = Meta(team=side, participants=(actor(taker, "taker"),), pos=spot, caused_by=caused_by)
    play.emit.emit(state, FreeKickEvent, meta, taker_id=taker.player_id, kind=kind)
    take_possession(state, taker, spot[0], spot[1])
    seconds = restart_delay(play, cfg.discipline.free_kick_s, cfg.discipline.free_kick_spread_s)
    if not cfg.restarts.enabled or kind == "indirect":
        return seconds
    direction = state.team(side).attack_dir
    frame_point = (frame_coordinate(spot[0], direction), frame_coordinate(spot[1], direction))
    roll = play.setpiece.u()
    if goal_distance_m(*frame_point) <= cfg.restarts.direct_range_m:
        if roll < cfg.restarts.direct_share:
            return seconds + _shoot(play, taker, frame_point)
    elif frame_point[0] >= _ATTACKING_HALF and roll < cfg.restarts.free_kick_cross_share:
        return seconds + deliver(play, side, taker)
    return seconds
