"""Off-ball movement: the slow loop that keeps players alive, pressing and goal-side marking.

Everything here is a pure function of the positions, the clock and the config: no random draws,
and no `sin`/`cos` (only exact arithmetic) so a match is identical on every platform
(docs/design/02 section 4). `positioning` combines these with the formation slots.
"""

from __future__ import annotations

from math import sqrt

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


def choose_pressers(
    team: TeamState, ball: Point, cfg: PositionConfig, *, keeper_has_it: bool = False
) -> tuple[int, ...]:
    """Return the slots of the outfield players who close the ball down, nearest first.

    A team that presses hard sends more men: `press_count` at average intensity. Only players
    within `press_range_m` go, the nearest always; one man shows a goalkeeper the way, no more.
    """
    count = max(1, round(cfg.press_count * (_PRESS_INTENSITY_FLOOR + team.view.press_intensity)))
    if keeper_has_it:
        count = 1
    ranked = sorted(
        (squared_distance_m(player.x, player.y, ball[0], ball[1]), player.slot)
        for player in team.players
        if player.line is not Line.KEEPER
    )
    reach = cfg.press_range_m**2
    chosen = [
        slot for index, (gap, slot) in enumerate(ranked[:count]) if index == 0 or gap <= reach
    ]
    return tuple(chosen)


def opponents_in_frame(team: TeamState, opponents: TeamState) -> list[tuple[PlayerState, Point]]:
    """The opponent outfielders as (player, position in the team's frame), keepers left out."""
    return [
        (
            rival,
            (
                frame_coordinate(rival.x, team.attack_dir),
                frame_coordinate(rival.y, team.attack_dir),
            ),
        )
        for rival in opponents.players
        if rival.line is not Line.KEEPER
    ]


def mark_spots(
    rivals: list[tuple[PlayerState, Point]],
    free: list[tuple[PlayerState, Point]],
    reach_m: float,
    goalside_m: float,
    taken: set[int],
) -> dict[int, Point]:
    """Pair each free defender with the rival nearest his slot within `reach_m`; return the spots.

    `rivals` come from `opponents_in_frame`; the spot is `goalside_m` goal-side of the man. Pairing
    is greedy in slot order and a man is marked once: `taken` holds the slots of rivals already
    marked and is filled in, so a second pass sees them.
    """
    spots: dict[int, Point] = {}
    reach = reach_m**2
    goalside = goalside_m / PITCH_LENGTH_M
    for player, slot_target in free:
        best: tuple[float, Point, int] | None = None
        for rival, spot in rivals:
            if rival.slot in taken:
                continue
            gap = squared_distance_m(slot_target[0], slot_target[1], spot[0], spot[1])
            if gap <= reach and (best is None or gap < best[0]):
                best = (gap, spot, rival.slot)
        if best is not None:
            taken.add(best[2])
            spots[player.slot] = (best[1][0] - goalside, best[1][1])
    return spots


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
    rivals = opponents_in_frame(team, opponents)
    return mark_spots(rivals, free, cfg.marking_range_m, cfg.marking_goalside_m, set())


def spread_out(
    aim: Point,
    crowd: list[tuple[int, float, float, float]],
    cfg: PositionConfig,
    own_slot: int = -1,
) -> Point:
    """Move a target away from team-mates standing too close to it (frame coordinates).

    `crowd` lists every team-mate as (slot, x, y, room): his place and the room he needs
    (`spacing_m`, or `carrier_space_m` for the man on the ball); `own_slot` is skipped. The push is
    the overlap times `spacing_push`, away from each, so a bunch spreads out and a lone player is
    left where he was.
    """
    x, y = aim
    # Perf: M8-sim-profile - this ran 20 times per position step and was 12% of a match through
    # distance_m calls and list building; the test is on squared metres and only a real overlap
    # takes a root.
    for slot, spot_x, spot_y, room in crowd:
        if slot == own_slot:
            continue
        dx = (aim[0] - spot_x) * PITCH_LENGTH_M
        dy = (aim[1] - spot_y) * PITCH_WIDTH_M
        gap_squared = dx * dx + dy * dy
        if gap_squared >= room * room:
            continue
        gap = sqrt(gap_squared)
        # Exactly on top of one another is split along the pitch; the order of `crowd` is stable.
        along = (dx / gap, dy / gap) if gap > 0 else (1.0, 0.0)
        shift = (room - gap) * cfg.spacing_push
        x += along[0] * shift / PITCH_LENGTH_M
        y += along[1] * shift / PITCH_WIDTH_M
    return x, y
