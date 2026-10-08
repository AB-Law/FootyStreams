"""Throw-ins and goal kicks: a named taker puts the ball back into play.

Which restart follows a ball that left the pitch is decided in `actions/out_of_play.py`; corners
(with the aerial duel) are in `actions/corner.py`.
"""

from __future__ import annotations

from footystreams.events.restarts import GoalKickEvent, ThrowInEvent
from footystreams.sim.actions.setpieces import restart_delay
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import CENTRE, Point, distance_m, frame_coordinate
from footystreams.sim.play import Play, actor, take_possession
from footystreams.sim.side import Side
from footystreams.sim.state import PlayerState, TeamState

GOAL_KICK_FRAME_X = 0.05  # the keeper places the ball near the six-yard box


def left_pitch(point: Point) -> bool:
    """True when an absolute point lies outside the pitch."""
    return not (0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0)


def overhit_point(start: Point, end: Point, distance_m_past: float) -> Point:
    """Return where a pass lands when it travels `distance_m_past` metres beyond its target."""
    length = distance_m(start[0], start[1], end[0], end[1])
    if length == 0.0:
        return end
    scale = distance_m_past / length
    return end[0] + (end[0] - start[0]) * scale, end[1] + (end[1] - start[1]) * scale


def nearest_outfielder(team: TeamState, spot: Point) -> PlayerState:
    """Return the team's outfield player closest to a point (the thrower or corner taker)."""
    outfield = [player for player in team.players if player is not team.keeper]
    return min(outfield, key=lambda p: (distance_m(spot[0], spot[1], p.x, p.y), p.slot))


def throw_in(play: Play, side: Side, spot: Point) -> float:
    """Restart with a throw-in for `side` at a touchline spot; return the stoppage seconds."""
    state, cfg = play.state, play.cfg.restarts
    taker = nearest_outfielder(state.team(side), spot)
    meta = Meta(team=side, participants=(actor(taker, "taker"),), pos=spot)
    play.emit.emit(state, ThrowInEvent, meta, taker_id=taker.player_id)
    take_possession(state, taker, spot[0], spot[1])
    return restart_delay(play, cfg.throw_in_s, cfg.throw_in_spread_s)


def goal_kick(play: Play, side: Side) -> float:
    """Restart with a goal kick taken by `side`'s keeper; return the stoppage seconds."""
    state, cfg = play.state, play.cfg.restarts
    team = state.team(side)
    keeper = team.keeper
    spot = (frame_coordinate(GOAL_KICK_FRAME_X, team.attack_dir), CENTRE)
    meta = Meta(team=side, participants=(actor(keeper, "taker"),), pos=spot)
    play.emit.emit(state, GoalKickEvent, meta, taker_id=keeper.player_id)
    take_possession(state, keeper, spot[0], spot[1])
    return restart_delay(play, cfg.goal_kick_s, cfg.goal_kick_spread_s)
