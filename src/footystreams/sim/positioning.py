"""Positioning: where the 22 players want to be and how they move there.

No physics engine: each player has a target derived from his formation slot, the tactics (line
height, width), whether his team has the ball and where the ball is; he moves toward it at a speed
set by pace, and never teleports except at dead-ball restarts (docs/design/02 section 4).
"""

from __future__ import annotations

from math import sqrt

from footystreams.sim.config import PositionConfig
from footystreams.sim.config_rules import OffsideConfig
from footystreams.sim.defending import plan_defending
from footystreams.sim.geometry import (
    CENTRE,
    PENALTY_AREA_DEPTH,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Point,
    frame_coordinate,
)
from footystreams.sim.mathx import PERCENT, clamp
from footystreams.sim.movement import choose_pressers, spread_out, wander
from footystreams.sim.offside import offside_line
from footystreams.sim.side import Side, opposite
from footystreams.sim.state import Line, MatchState, PlayerState, TeamState
from footystreams.sim.support import support_spots, support_weight

# Share of the line-height shift and the push/drop each row takes: GK, defence, mid, attack.
_LINE_SHIFT_WEIGHT = (0.0, 1.0, 0.6, 0.3)
_MAX_TARGET_FRAME_X = 0.98
_MIN_TARGET_FRAME_X = 0.02
KICKOFF_MAX_X = 0.49  # nobody but the taker is in the opponent's half at kick-off


def target_in_frame(
    team: TeamState,
    player: PlayerState,
    ball: tuple[float, float],
    in_possession: bool,  # noqa: FBT001 - internal helper, called from one place
    cfg: PositionConfig,
) -> tuple[float, float]:
    """Return the point (in the team's frame) this player is drawn toward right now."""
    weight = _LINE_SHIFT_WEIGHT[player.line]
    push = cfg.push_in_possession if in_possession else -cfg.drop_out_of_possession
    shift = (team.view.line_height - CENTRE) * cfg.line_range
    target_x = player.base_x + (push + shift) * weight
    target_x += cfg.pull_x[player.line] * (ball[0] - target_x)
    width = cfg.width_min + (cfg.width_max - cfg.width_min) * team.view.width
    target_y = CENTRE + (player.base_y - CENTRE) * width
    target_y += cfg.pull_y * (ball[1] - target_y)
    return clamp(target_x, _MIN_TARGET_FRAME_X, _MAX_TARGET_FRAME_X), clamp(
        target_y, cfg.edge_margin, 1.0 - cfg.edge_margin
    )


def speed_mps(player: PlayerState, cfg: PositionConfig) -> float:
    """Return how fast the player can move toward his target, in metres per second."""
    return cfg.base_speed_mps + cfg.speed_range_mps * player.skills.pace / PERCENT


def move_toward(player: PlayerState, target_x: float, target_y: float, max_metres: float) -> None:
    """Move a player toward an absolute target by at most `max_metres`, never overshooting."""
    dx = (target_x - player.x) * PITCH_LENGTH_M
    dy = (target_y - player.y) * PITCH_WIDTH_M
    remaining = sqrt(dx * dx + dy * dy)
    if remaining <= max_metres:
        player.x, player.y = target_x, target_y
        return
    fraction = max_metres / remaining
    player.x += (target_x - player.x) * fraction
    player.y += (target_y - player.y) * fraction


def ceiling_below_line(line: float, player: PlayerState, cfg: OffsideConfig) -> float:
    """Return the farthest frame x this player will stand, given the offside line.

    Sharper off-the-ball movers (higher `off_ball_movement`) hug the line more tightly.
    """
    margin = cfg.margin_min + cfg.margin_range * (1.0 - player.skills.off_ball_movement / PERCENT)
    return line - margin


def offside_ceiling(
    team: TeamState, opponents: TeamState, player: PlayerState, cfg: OffsideConfig
) -> float:
    """Return the farthest frame x this player will stand: just short of the offside line."""
    return ceiling_below_line(offside_line(opponents, team.attack_dir), player, cfg)


Move = tuple[PlayerState, float, float, float]  # player, absolute target x, y, metres allowed
Intent = tuple[PlayerState, Point, float]  # player, target in the team's frame, sprint factor


def _inside(point: Point, cfg: PositionConfig) -> Point:
    """Keep a target on the pitch, off the touchlines by the edge margin."""
    # Perf: M8-sim-profile - called for every player every step; plain comparisons beat clamp().
    x, y = point
    low, high = cfg.edge_margin, 1.0 - cfg.edge_margin
    x = _MIN_TARGET_FRAME_X if x < _MIN_TARGET_FRAME_X else min(x, _MAX_TARGET_FRAME_X)
    y = low if y < low else min(y, high)
    return x, y


def _toward(slot: Point, spot: Point | None, weight: float) -> Point:
    """Blend a slot target toward the spot beside the man a defender marks (when he has one)."""
    if spot is None:
        return slot
    return slot[0] + weight * (spot[0] - slot[0]), slot[1] + weight * (spot[1] - slot[1])


def _crowd(
    state: MatchState, team: TeamState, cfg: PositionConfig
) -> list[tuple[int, float, float, float]]:
    """Each team-mate as (slot, x, y, room): his place in the team's frame and the room he needs."""
    flip = team.attack_dir < 0
    return [
        (
            player.slot,
            1.0 - player.x if flip else player.x,
            1.0 - player.y if flip else player.y,
            cfg.carrier_space_m if player is state.carrier else cfg.spacing_m,
        )
        for player in team.players
    ]


def _cover_spots(close_in: Point, ball: Point, count: int, cfg: PositionConfig) -> list[Point]:
    """Where each presser goes: the first on the ball, the others covering behind and inside.

    Without this they all aim at one spot, arrive together and stand in a heap on the carrier.
    """
    toward_middle = 1.0 if ball[1] < CENTRE else -1.0
    spots = [close_in]
    for rank in range(1, count):
        depth = rank * cfg.cover_depth_m / PITCH_LENGTH_M
        side = (rank if rank % 2 else -rank) * cfg.cover_width_m / PITCH_WIDTH_M
        spots.append((close_in[0] - depth, ball[1] + toward_middle * side))
    return spots


def _frame_spot(player: PlayerState, team: TeamState) -> Point:
    return frame_coordinate(player.x, team.attack_dir), frame_coordinate(player.y, team.attack_dir)


def _roles(
    state: MatchState,
    team: TeamState,
    slots: list[tuple[PlayerState, Point]],
    cfg: PositionConfig,
    *,
    in_possession: bool,
) -> tuple[tuple[int, ...], dict[int, tuple[Point, float]]]:
    """Who presses, and the spot and weight each other player's job pulls him toward."""
    ball = (
        _frame_spot(state.carrier, team)
        if in_possession
        else (
            frame_coordinate(state.ball_x, team.attack_dir),
            frame_coordinate(state.ball_y, team.attack_dir),
        )
    )
    opponents = state.team(opposite(team.side))
    if in_possession:
        movers = [
            (player, _frame_spot(player, team))
            for player, _ in slots
            if player.line is not Line.KEEPER
        ]
        rivals = [_frame_spot(rival, team) for rival in opponents.players]
        spots = support_spots(movers, ball, rivals, cfg)
        by_slot = {player.slot: player for player, _ in slots}
        return (), {s: (spot, support_weight(by_slot[s], cfg)) for s, spot in spots.items()}
    keeper_has_it = state.carrier.line is Line.KEEPER
    pressers = choose_pressers(team, (state.ball_x, state.ball_y), cfg, keeper_has_it=keeper_has_it)
    reach = (1.0 - PENALTY_AREA_DEPTH) if keeper_has_it else _MAX_TARGET_FRAME_X
    close_in = (min(ball[0] - cfg.press_gap_m / PITCH_LENGTH_M, reach), ball[1])
    free = [(p, t) for p, t in slots if p.slot not in pressers and cfg.marking_weight[p.line]]
    return pressers, plan_defending(team, opponents, free, (ball, close_in), cfg)


def _intents(
    state: MatchState, team: TeamState, cfg: PositionConfig, *, in_possession: bool
) -> list[Intent]:
    """Where each player (not the carrier) wants to be: slot, job, or ball, plus his own loop."""
    ball = (
        frame_coordinate(state.ball_x, team.attack_dir),
        frame_coordinate(state.ball_y, team.attack_dir),
    )
    slots = [
        (player, target_in_frame(team, player, ball, in_possession, cfg))
        for player in team.players
        if player is not state.carrier
    ]
    pressers, jobs = _roles(state, team, slots, cfg, in_possession=in_possession)
    reach = (1.0 - PENALTY_AREA_DEPTH) if state.carrier.line is Line.KEEPER else _MAX_TARGET_FRAME_X
    close_in = (min(ball[0] - cfg.press_gap_m / PITCH_LENGTH_M, reach), ball[1])
    cover = _cover_spots(close_in, ball, len(pressers), cfg)
    crowd = _crowd(state, team, cfg)
    intents: list[Intent] = []
    for player, slot in slots:
        if player.slot in pressers:
            spot = cover[pressers.index(player.slot)]
            intents.append((player, _inside(spot, cfg), cfg.press_speed_bonus))
            continue
        spot, weight = jobs.get(player.slot, (slot, 0.0))
        aim = _toward(slot, spot, weight)
        loop = wander(player, state.elapsed_s, in_possession=in_possession, cfg=cfg)
        wanted = (aim[0] + loop[0], aim[1] + loop[1])
        spread = spread_out(wanted, crowd, cfg, own_slot=player.slot)
        intents.append((player, _inside(spread, cfg), 1.0))
    return intents


def _plan_team_moves(
    state: MatchState,
    team: TeamState,
    dt: float,
    rules: tuple[PositionConfig, OffsideConfig | None],
) -> list[Move]:
    cfg, offside = rules
    opponents = state.team(opposite(team.side))
    in_possession = team.side == state.carrier.side
    # Perf: M8-sim-profile - the line is the same for every player of the team in one planning
    # pass (nobody has moved yet), so it is found once instead of once per player (was 11% of CPU).
    line = offside_line(opponents, team.attack_dir) if offside is not None else 0.0
    moves: list[Move] = []
    flip = team.attack_dir < 0
    for player, target, sprint in _intents(state, team, cfg, in_possession=in_possession):
        ceiling = ceiling_below_line(line, player, offside) if offside is not None else 1.0
        frame_x = target[0] if player.line is Line.KEEPER else min(target[0], ceiling)
        moves.append(
            (
                player,
                1.0 - frame_x if flip else frame_x,
                1.0 - target[1] if flip else target[1],
                speed_mps(player, cfg) * sprint * dt,
            )
        )
    return moves


def update_positions(
    state: MatchState, dt: float, cfg: PositionConfig, offside: OffsideConfig | None = None
) -> None:
    """Move every player except the ball carrier toward his target for `dt` seconds.

    With `offside` given, attackers stay behind the opponents' second-last defender. Both teams
    plan from the same positions and then move, so neither side reacts to the other's step.
    """
    moves = [
        move
        for team in (state.home, state.away)
        for move in _plan_team_moves(state, team, dt, (cfg, offside))
    ]
    for player, target_x, target_y, metres in moves:
        move_toward(player, target_x, target_y, metres)
    if offside is not None:
        _hold_the_line(state, offside)


def _hold_the_line(state: MatchState, cfg: OffsideConfig) -> None:
    """Pull back any attacker the opponents' line has left behind it.

    The ceiling in `_plan_team_moves` only limits where a player is heading; a defence that drops
    leaves attackers standing offside until they walk back, which was half of all offsides
    (M8 sweep). Players watch the line, so being beyond it is not a state they stay in; offsides
    come from the mistimed runs of `actions/offside.py` alone. Both lines are read before either
    team is pulled back so the result does not depend on the team order.
    """
    lines = {
        team.side: offside_line(state.team(opposite(team.side)), team.attack_dir)
        for team in (state.home, state.away)
    }
    for team in (state.home, state.away):
        for player in team.players:
            if player is state.carrier or player.line is Line.KEEPER:
                continue
            ceiling = ceiling_below_line(lines[team.side], player, cfg)
            if frame_coordinate(player.x, team.attack_dir) > ceiling:
                player.x = frame_coordinate(ceiling, team.attack_dir)


def place_for_kickoff(state: MatchState, kicking_side: Side) -> None:
    """Put everyone on his slot (own half only) and the kicker on the centre spot with the ball."""
    for team in (state.home, state.away):
        for player in team.players:
            frame_x = min(player.base_x, KICKOFF_MAX_X)
            player.x = frame_coordinate(frame_x, team.attack_dir)
            player.y = frame_coordinate(player.base_y, team.attack_dir)
    kicking = state.team(kicking_side)
    taker = max(kicking.players, key=lambda player: (player.line, player.base_x, -player.slot))
    taker.x, taker.y = CENTRE, CENTRE
    state.carrier = taker
    state.ball_x, state.ball_y = CENTRE, CENTRE
