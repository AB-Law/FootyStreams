"""Off-ball movement: the slow loop that keeps players alive, pressing and goal-side marking.

Everything here is a pure function of the positions, the clock and the config: no random draws,
and no `sin`/`cos` (only exact arithmetic) so a match is identical on every platform
(docs/design/02 section 4). `positioning` combines these with the formation slots.
"""

from __future__ import annotations

from footystreams.sim.config import PositionConfig
from footystreams.sim.geometry import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Point,
    frame_coordinate,
    squared_distance_m,
)
from footystreams.sim.mathx import PERCENT
from footystreams.sim.state import Line, PlayerState, TeamState

_PHASE_STEP = 0.381966  # golden-ratio conjugate: spreads the slots evenly round the cycle
_AWAY_PHASE = 0.5
_Y_RATE = 1.3  # the sideways loop runs at a different rate, so the path is a Lissajous curve
_ACTIVITY_FLOOR = 0.5  # share of the loop even the laziest mover makes
_OUT_OF_POSSESSION_ACTIVITY = 0.5
_PRESS_INTENSITY_FLOOR = 0.5
_TRIANGLE_PEAK = 2.0
_QUARTER = 4.0


def _wave(cycle: float) -> float:
    """Smooth wave in [-1, 1] with period 1 (a triangle wave eased at its turning points)."""
    folded = abs(_QUARTER * (cycle % 1.0) - _TRIANGLE_PEAK) - 1.0
    return folded * (1.5 - 0.5 * folded * folded)


def wander(
    player: PlayerState, elapsed_s: float, *, in_possession: bool, cfg: PositionConfig
) -> Point:
    """Return the (x, y) offset, in frame units, of the loop a player runs round his target.

    Sharper off-the-ball movers loop wider while their team has the ball; forwards move most.
    """
    reach_m = cfg.wander_m[player.line]
    if reach_m == 0.0:
        return 0.0, 0.0
    if in_possession:
        activity = _ACTIVITY_FLOOR + player.skills.off_ball_movement / PERCENT
    else:
        activity = _OUT_OF_POSSESSION_ACTIVITY
    phase = player.slot * _PHASE_STEP + (_AWAY_PHASE if player.side == "away" else 0.0)
    cycle = elapsed_s / cfg.wander_period_s + phase
    scale = reach_m * activity
    return (
        scale * _wave(cycle) / PITCH_LENGTH_M,
        scale * _wave(_Y_RATE * cycle + phase) / PITCH_WIDTH_M,
    )


def choose_pressers(team: TeamState, ball: Point, cfg: PositionConfig) -> frozenset[int]:
    """Return the slots of the outfield players who close the ball down (nearest first).

    A team that presses hard sends more men: `press_count` at average intensity.
    """
    count = max(1, round(cfg.press_count * (_PRESS_INTENSITY_FLOOR + team.view.press_intensity)))
    ranked = sorted(
        (squared_distance_m(player.x, player.y, ball[0], ball[1]), player.slot)
        for player in team.players
        if player.line is not Line.KEEPER
    )
    return frozenset(slot for _, slot in ranked[:count])


def assign_marks(
    team: TeamState,
    opponents: TeamState,
    free: list[tuple[PlayerState, Point]],
    cfg: PositionConfig,
) -> dict[int, Point]:
    """Pair each free defender with the opponent nearest his slot; return the goal-side spots.

    `free` is each marker's slot target in the team's frame. Pairing is greedy in slot order and a
    man is marked by one player only; the keeper is never marked. Spots are in the team's frame.
    """
    taken: set[int] = set()
    spots: dict[int, Point] = {}
    reach = cfg.marking_range_m**2
    goalside = cfg.marking_goalside_m / PITCH_LENGTH_M
    for player, slot_target in free:
        best: tuple[float, PlayerState] | None = None
        for rival in opponents.players:
            if rival.slot in taken or rival.line is Line.KEEPER:
                continue
            gap = squared_distance_m(
                slot_target[0],
                slot_target[1],
                frame_coordinate(rival.x, team.attack_dir),
                frame_coordinate(rival.y, team.attack_dir),
            )
            if gap <= reach and (best is None or gap < best[0]):
                best = (gap, rival)
        if best is not None:
            rival = best[1]
            taken.add(rival.slot)
            spots[player.slot] = (
                frame_coordinate(rival.x, team.attack_dir) - goalside,
                frame_coordinate(rival.y, team.attack_dir),
            )
    return spots
