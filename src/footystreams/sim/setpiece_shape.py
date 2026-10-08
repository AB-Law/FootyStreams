"""Set-piece shapes: where the 22 stand for a throw-in, goal kick, corner, free kick or penalty.

A dead ball gives the players seconds to organise, and a match that shows nobody doing so looks
frozen. `arrange` places the men involved (the rest keep their normal places) and moves them there
at their own pace for as long as the stoppage lasts, so frames show them walking into the shape.
Everything is worked out in the taking team's frame (x toward the goal it attacks); positions are
pure functions of the state, and no random number is drawn (docs/design/02 section 6).
"""

from __future__ import annotations

from math import sqrt

from footystreams.sim.geometry import (
    CENTRE,
    PENALTY_AREA_DEPTH,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Point,
    frame_coordinate,
)
from footystreams.sim.play import Play
from footystreams.sim.positioning import move_toward, speed_mps
from footystreams.sim.side import opposite
from footystreams.sim.state import Line, MatchState, PlayerState, TeamState

Placement = tuple[PlayerState, Point]  # a player and where he stands, in the taking team's frame

WALL_DISTANCE_M = 9.15
WALL_SPACING_M = 0.9
WALL_MIN_SIZE = 3
LONG_WALL_FROM_M = 20.0
THROW_OPTIONS = ((0.05, 0.04), (-0.04, 0.14), (0.14, 0.18))  # (along, inward) from the thrower
MARK_GOALSIDE = 0.015
BOX_ARC_X = 1.0 - PENALTY_AREA_DEPTH - 0.04  # outside the box for a penalty
PENALTY_ROW_GAP = 0.05  # the defending side stands a row behind the taking side
SHORT_CORNER_FLANK = 0.75
GOAL_LINE_X = 0.99
HOLD_BACK_X = 0.5  # the centre-backs who stay up the pitch at an attacking set piece


def sqrt_of_squares(dx: float, dy: float) -> float:
    """Return the length of a vector (`sqrt` is exact and portable; `hypot` is not)."""
    return sqrt(dx * dx + dy * dy)


def _outfield(team: TeamState) -> list[PlayerState]:
    return [player for player in team.players if player.line is not Line.KEEPER]


def _frame_point(team: TeamState, player: PlayerState) -> Point:
    return (
        frame_coordinate(player.x, team.attack_dir),
        frame_coordinate(player.y, team.attack_dir),
    )


def _gap_m(a: Point, b: Point) -> float:
    return sqrt_of_squares((a[0] - b[0]) * PITCH_LENGTH_M, (a[1] - b[1]) * PITCH_WIDTH_M)


def _nearest(
    taking: TeamState, players: list[PlayerState], spot: Point, count: int
) -> list[PlayerState]:
    """The `count` players closest to a point of the taking team's frame, nearest first."""
    ranked = sorted(players, key=lambda p: (_gap_m(_frame_point(taking, p), spot), p.slot))
    return ranked[:count]


def _aerial(player: PlayerState) -> float:
    skills = player.skills
    return 0.5 * skills.heading + 0.3 * skills.jumping_reach + 0.2 * skills.off_ball_movement


def _mark(taking: TeamState, markers: list[PlayerState], spots: list[Point]) -> list[Placement]:
    """Each spot gets the nearest free marker, standing a step goal-side of it."""
    free = list(markers)
    placed: list[Placement] = []
    for spot in spots:
        if not free:
            break
        marker = _nearest(taking, free, spot, 1)[0]
        free.remove(marker)
        placed.append((marker, (min(spot[0] + MARK_GOALSIDE, 1.0), spot[1])))
    return placed


def _outlets(taking: TeamState, taker: PlayerState, spot: Point) -> list[Placement]:
    """Three team-mates offer themselves round the man taking a throw or a short free kick."""
    inward = 1.0 if spot[1] < CENTRE else -1.0
    mates = _nearest(
        taking, [p for p in _outfield(taking) if p is not taker], spot, len(THROW_OPTIONS)
    )
    return [
        (mate, (spot[0] + along, spot[1] + inward * across))
        for mate, (along, across) in zip(mates, THROW_OPTIONS, strict=False)
    ]


def throw_in_layout(
    state: MatchState, taking: TeamState, taker: PlayerState, spot: Point
) -> list[Placement]:
    """Team-mates show for the throw and the nearest opponents pick them up."""
    options = _outlets(taking, taker, spot)
    defending = state.team(opposite(taking.side))
    return [*options, *_mark(taking, _outfield(defending), [point for _, point in options])]


def goal_kick_layout(state: MatchState, taking: TeamState) -> list[Placement]:
    """The taking side spreads from the keeper up the pitch; the other side presses high."""
    placed: list[Placement] = []
    rows = {Line.DEFENCE: 0.22, Line.MIDFIELD: 0.48, Line.ATTACK: 0.66}
    for line, x in rows.items():
        group = sorted((p for p in taking.players if p.line is line), key=lambda p: p.slot)
        for index, player in enumerate(group):
            placed.append((player, (x, (index + 1) / (len(group) + 1))))
    pressing = state.team(opposite(taking.side))
    forwards = sorted((p for p in pressing.players if p.line is Line.ATTACK), key=lambda p: p.slot)
    for index, player in enumerate(forwards):
        placed.append((player, (0.26, (index + 1) / (len(forwards) + 1))))
    return placed


def _flank(flag_y: float, share: float) -> float:
    """A lateral place `share` of the way from the middle toward the corner's side."""
    return CENTRE + (flag_y - CENTRE) * share


def corner_layout(
    state: MatchState, taking: TeamState, taker: PlayerState, flag: Point, wanted: int
) -> list[Placement]:
    """Attackers crowd the box, one stays short, defenders post up and pick up their men."""
    flag_y = frame_coordinate(flag[1], taking.attack_dir)
    pool = sorted(
        (p for p in _outfield(taking) if p is not taker), key=lambda p: (-_aerial(p), p.slot)
    )
    spots = [
        (0.95, _flank(flag_y, 0.12)),
        (0.90, CENTRE),
        (0.95, _flank(flag_y, -0.12)),
        (0.86, _flank(flag_y, 0.25)),
        (0.86, _flank(flag_y, -0.25)),
        (0.82, CENTRE),
    ][: max(wanted, 1)]
    attackers = list(zip(pool, spots, strict=False))
    placed: list[Placement] = [(player, spot) for player, spot in attackers]
    short = next((p for p in pool[len(attackers) :] if p.line is not Line.DEFENCE), None)
    if short is not None:
        placed.append((short, (0.97, _flank(flag_y, SHORT_CORNER_FLANK))))
    placed.extend(_defend_box(state, taking, [spot for _, spot in attackers], flag_y))
    return placed


def _defend_box(
    state: MatchState, taking: TeamState, targets: list[Point], flag_y: float
) -> list[Placement]:
    """The keeper on his line, two on the posts and the best aerial defenders on the attackers."""
    defending = state.team(opposite(taking.side))
    men = sorted(_outfield(defending), key=lambda p: (-p.skills.heading - p.skills.marking, p.slot))
    placed: list[Placement] = [(defending.keeper, (GOAL_LINE_X, _flank(flag_y, 0.06)))]
    for post, share in zip(men[:2], (0.2, -0.2), strict=False):
        placed.append((post, (GOAL_LINE_X, _flank(flag_y, share))))
    placed.extend(_mark(taking, men[2:], targets))
    return placed


def free_kick_layout(
    state: MatchState, taking: TeamState, taker: PlayerState, spot: Point, *, shooting: bool
) -> list[Placement]:
    """A wall and a crowd in the box for a kick at goal; otherwise outlets round the taker."""
    if not shooting:
        return _outlets(taking, taker, spot)
    defending = state.team(opposite(taking.side))
    run = ((1.0 - spot[0]) * PITCH_LENGTH_M, (CENTRE - spot[1]) * PITCH_WIDTH_M)
    length = sqrt_of_squares(*run) or 1.0
    unit = (run[0] / length, run[1] / length)
    centre = (
        spot[0] + unit[0] * WALL_DISTANCE_M / PITCH_LENGTH_M,
        spot[1] + unit[1] * WALL_DISTANCE_M / PITCH_WIDTH_M,
    )
    size = WALL_MIN_SIZE + (1 if length > LONG_WALL_FROM_M else 0)
    wall = _nearest(
        taking, [p for p in _outfield(defending) if p.line is not Line.ATTACK], centre, size
    )
    placed: list[Placement] = []
    for index, player in enumerate(wall):
        offset = (index - (size - 1) / 2.0) * WALL_SPACING_M
        placed.append(
            (
                player,
                (
                    centre[0] - unit[1] * offset / PITCH_LENGTH_M,
                    centre[1] + unit[0] * offset / PITCH_WIDTH_M,
                ),
            )
        )
    placed.append((defending.keeper, (GOAL_LINE_X, CENTRE + (spot[1] - CENTRE) * 0.2)))
    crowd = sorted(
        (p for p in _outfield(taking) if p is not taker), key=lambda p: (-_aerial(p), p.slot)
    )[:3]
    spots = [(0.90, 0.42), (0.90, CENTRE), (0.90, 0.58)]
    placed.extend(zip(crowd, spots, strict=False))
    rest = [p for p in _outfield(defending) if p not in wall]
    placed.extend(_mark(taking, rest, spots[: len(crowd)]))
    return placed


def penalty_layout(state: MatchState, taking: TeamState, taker: PlayerState) -> list[Placement]:
    """Everyone but the taker and the keeper waits outside the box; the keeper is on his line."""
    defending = state.team(opposite(taking.side))
    placed: list[Placement] = [(defending.keeper, (GOAL_LINE_X, CENTRE))]
    rows = (
        ([p for p in _outfield(taking) if p is not taker], BOX_ARC_X),
        (_outfield(defending), BOX_ARC_X - PENALTY_ROW_GAP),
    )
    for waiting, x in rows:
        for index, player in enumerate(waiting):
            placed.append((player, (x, (index + 1) / (len(waiting) + 1))))
    return placed


def settle(
    play: Play, taking: TeamState, placed: list[Placement], seconds: float, *, keyframe: bool
) -> None:
    """Walk each placed player toward his spot at his own pace for `seconds`.

    With `keyframe` (a set piece whose kick is resolved in the same moment) the arrangement is
    also recorded as a mid-moment snapshot when frames are on, so they show the build-up and
    then the kick instead of one blend of both.
    """
    state, cfg = play.state, play.cfg.positioning
    for player, (fx, fy) in placed:
        target = (frame_coordinate(fx, taking.attack_dir), frame_coordinate(fy, taking.attack_dir))
        move_toward(player, target[0], target[1], speed_mps(player, cfg) * seconds)
    if keyframe and state.record_keyframes:
        state.keyframes.append(state.keyframe(state.t_period + seconds))
