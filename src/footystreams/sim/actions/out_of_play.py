"""What follows a ball that left the pitch: throw-in, goal kick or corner."""

from __future__ import annotations

from footystreams.sim.actions.corner import corner
from footystreams.sim.actions.restarts import goal_kick, throw_in
from footystreams.sim.geometry import CENTRE, Point
from footystreams.sim.mathx import clamp
from footystreams.sim.play import Play
from footystreams.sim.side import Side, opposite


def defending_side_of_goal(play: Play, goal_x: float) -> Side:
    """Return the side that defends the goal at absolute x (>= 0.5 means the x = 1 goal)."""
    attack_dir = -1 if goal_x >= CENTRE else 1
    return "home" if play.state.home.attack_dir == attack_dir else "away"


def out_of_play(play: Play, exit_point: Point, last_touch: Side) -> float:
    """Restart after the ball left the pitch at `exit_point`; return the stoppage seconds.

    Over a touchline: a throw-in to the side that did not touch it last. Over a goal line: a goal
    kick if the attackers touched it last, a corner if the defenders did.
    """
    x, y = exit_point
    if y < 0.0 or y > 1.0:
        spot = (clamp(x, 0.0, 1.0), 0.0 if y < 0.0 else 1.0)
        return throw_in(play, opposite(last_touch), spot)
    defenders = defending_side_of_goal(play, x)
    if last_touch == defenders:
        flag = (1.0 if x >= CENTRE else 0.0, 0.0 if y < CENTRE else 1.0)
        return corner(play, opposite(defenders), flag)
    return goal_kick(play, defenders)
