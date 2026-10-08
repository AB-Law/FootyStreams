"""How a shot travels: where it ends, how much it bends, how hard it is hit and how high it flies.

Pure presentation data for the broadcast (the outcome is decided in `actions/resolve_shot.py`
and never changes here): the draws come from their own `flight` stream, so adding or tuning this
never moves another random stream and the match is the same with or without it. Four draws per
shot, whatever the outcome, keep the stream aligned (docs/design/02 section 5.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.sim.geometry import GOAL_WIDTH_M, PITCH_LENGTH_M, PITCH_WIDTH_M, Point
from footystreams.sim.mathx import PERCENT, clamp
from footystreams.sim.play import Play
from footystreams.sim.state import PlayerState

HALF_GOAL = GOAL_WIDTH_M / 2.0 / PITCH_WIDTH_M  # half the goal mouth, as a fraction of the width
_CENTRE = 0.5
_FAIR_COIN = 0.5
_INSIDE_POST_SHARE = 0.85  # a goal is placed this far toward a post at most
_WIDE_MIN = 0.012  # a miss is at least this far outside the post (fraction of width)
_WIDE_RANGE = 0.05
_BLOCK_SHARE = 0.3  # a blocked shot is stopped this far along its line
_KEEPER_REACH = 0.02  # a save ends this far (fraction of width) from where the keeper stands
_CURVE_DISTANCE_M = 25.0  # from this far out a shot can bend fully
_MIN_CURVE = 0.1
_CURVE_SKILL_RANGE = 0.7
_STRAIGHT_BELOW = 0.2  # share of shots hit straight, without bend
_OPPOSITE_BELOW = 0.35  # share (cumulative) that bend the other way
_BASE_SPEED_MPS = 20.0
_SPEED_RANGE_MPS = 14.0
_CHIP_DISTANCE_M = 30.0
_MIN_LOFT = 0.08
_LOFT_RANGE = 0.4


@dataclass(frozen=True, slots=True)
class ShotFlight:
    """The path of one shot: end point (absolute), bend in [-1, 1], pace and loft in [0, 1]."""

    target: Point
    curve: float
    speed_mps: float
    loft: float


def _skill(shooter: PlayerState) -> float:
    """The striker's finishing and long-shot ability as a share of the scale."""
    return (shooter.skills.finishing + shooter.skills.long_shots) / (2.0 * PERCENT)


def _target(
    outcome: str,
    goal_x: float,
    shooters: tuple[PlayerState, PlayerState],
    draws: tuple[float, float],
) -> Point:
    """Where the ball ends up, from the outcome (absolute coordinates)."""
    shooter, keeper = shooters
    side = 1.0 if draws[0] < _FAIR_COIN else -1.0
    if outcome == "goal":
        return goal_x, _CENTRE + side * _INSIDE_POST_SHARE * HALF_GOAL * draws[1]
    if outcome == "woodwork":
        return goal_x, _CENTRE + side * HALF_GOAL
    if outcome == "saved":
        return goal_x, clamp(keeper.y + side * _KEEPER_REACH * draws[1], 0.0, 1.0)
    if outcome == "blocked":
        return (
            shooter.x + (goal_x - shooter.x) * _BLOCK_SHARE,
            shooter.y + (_CENTRE - shooter.y) * _BLOCK_SHARE,
        )
    wide = HALF_GOAL + _WIDE_MIN + _WIDE_RANGE * draws[1]
    return goal_x, clamp(_CENTRE + side * wide, 0.0, 1.0)


def _curve(shooter: PlayerState, target: Point, draws: tuple[float, float]) -> float:
    """Bend of the shot: skilled strikers from distance bend it round the keeper, mostly inward."""
    if draws[0] < _STRAIGHT_BELOW:
        return 0.0
    distance_m = abs(target[0] - shooter.x) * PITCH_LENGTH_M
    reach = clamp(distance_m / _CURVE_DISTANCE_M, 0.0, 1.0)
    size = clamp(_MIN_CURVE + _CURVE_SKILL_RANGE * _skill(shooter) * reach * draws[1], 0.0, 1.0)
    # The path bows toward the touchline on the shooter's side, then comes back in.
    outside = 1.0 if shooter.y >= _CENTRE else -1.0
    along_x = 1.0 if target[0] > shooter.x else -1.0
    inward = draws[0] >= _OPPOSITE_BELOW
    return outside * along_x * size * (1.0 if inward else -1.0)


def shot_flight(play: Play, shooter: PlayerState, outcome: str) -> ShotFlight:
    """Return the flight of a shot just resolved with `outcome` (four draws from `flight`)."""
    state = play.state
    goal_x = 1.0 if state.attackers.attack_dir > 0 else 0.0
    side, place, bend, power = (play.flight.u() for _ in range(4))
    target = _target(outcome, goal_x, (shooter, state.defenders.keeper), (side, place))
    distance_m = abs(goal_x - shooter.x) * PITCH_LENGTH_M
    speed = _BASE_SPEED_MPS + _SPEED_RANGE_MPS * clamp(
        _FAIR_COIN * _skill(shooter) + _FAIR_COIN * power, 0.0, 1.0
    )
    chip = clamp(distance_m / _CHIP_DISTANCE_M, 0.0, 1.0)
    return ShotFlight(
        target=target,
        curve=_curve(shooter, target, (bend, place)),
        speed_mps=round(speed, 1),
        loft=round(_MIN_LOFT + _LOFT_RANGE * chip * power, 2),
    )
