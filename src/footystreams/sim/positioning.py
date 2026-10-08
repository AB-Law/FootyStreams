"""Positioning: where the 22 players want to be and how they move there.

No physics engine: each player has a target derived from his formation slot, the tactics (line
height, width), whether his team has the ball and where the ball is; he moves toward it at a speed
set by pace, and never teleports except at dead-ball restarts (docs/design/02 section 4).
"""

from __future__ import annotations

from math import sqrt

from footystreams.sim.config import PositionConfig
from footystreams.sim.config_rules import OffsideConfig
from footystreams.sim.geometry import CENTRE, PITCH_LENGTH_M, PITCH_WIDTH_M, frame_coordinate
from footystreams.sim.mathx import PERCENT, clamp
from footystreams.sim.offside import offside_line
from footystreams.sim.side import Side, opposite
from footystreams.sim.state import Line, MatchState, PlayerState, TeamState

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
    return clamp(target_x, _MIN_TARGET_FRAME_X, _MAX_TARGET_FRAME_X), clamp(target_y, 0.0, 1.0)


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


def _plan_team_moves(
    state: MatchState,
    team: TeamState,
    dt: float,
    rules: tuple[PositionConfig, OffsideConfig | None],
) -> list[Move]:
    cfg, offside = rules
    opponents = state.team(opposite(team.side))
    in_possession = team.side == state.carrier.side
    ball = (
        frame_coordinate(state.ball_x, team.attack_dir),
        frame_coordinate(state.ball_y, team.attack_dir),
    )
    # Perf: M8-sim-profile - the line is the same for every player of the team in one planning
    # pass (nobody has moved yet), so it is found once instead of once per player (was 11% of CPU).
    line = offside_line(opponents, team.attack_dir) if offside is not None else 0.0
    moves: list[Move] = []
    for player in team.players:
        if player is state.carrier:
            continue
        target_x, target_y = target_in_frame(team, player, ball, in_possession, cfg)
        if offside is not None and player.line is not Line.KEEPER:
            target_x = min(target_x, ceiling_below_line(line, player, offside))
        moves.append(
            (
                player,
                frame_coordinate(target_x, team.attack_dir),
                frame_coordinate(target_y, team.attack_dir),
                speed_mps(player, cfg) * dt,
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
