"""Corners: the taker, the delivery and the aerial duel (docs/design/02 section 6).

The attackers sent into the box (`corner_attackers` of the tactics) are compared with the best
defenders: their share of the aerial strength, lifted by the taker's delivery, decides whether the
keeper claims, an attacker gets a header away, or the defence clears. Draws come from `setpiece`.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.events.open_play import ClearanceEvent
from footystreams.events.restarts import CornerEvent
from footystreams.sim.actions.restarts import GOAL_KICK_FRAME_X, nearest_outfielder
from footystreams.sim.actions.setpieces import restart_delay
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import CENTRE, Point, frame_coordinate
from footystreams.sim.mathx import PERCENT, clamp, squash
from footystreams.sim.options import ActionKind, Option
from footystreams.sim.play import Play, actor, take_possession
from footystreams.sim.setpiece_shape import corner_layout, settle
from footystreams.sim.side import Side, opposite
from footystreams.sim.state import PlayerState, TeamState

DEFENDERS_IN_BOX = 5
HEADER_FRAME_X = 0.93  # where a header is taken, in the attackers' frame
HEADER_PRESSURE = 0.5
SECOND_BALL_ATTACKER_SHARE = 0.40
CLEARANCE_FRAME_X = 0.74  # the top of the box: a headed clearance carries 25 m or so, not 70
DELIVERY_PIVOT = 55.0
DELIVERY_SCALE = 25.0
CLAIM_BASE = 1.5  # keeper claims more often when the attackers' share is small


@dataclass(frozen=True, slots=True)
class Duel:
    """The aerial contest at a corner: who is in it and the attackers' share of it."""

    attackers: list[PlayerState]
    defenders: list[PlayerState]
    share: float  # attackers' share of the aerial strength after delivery, 0-1


def choose_corner_taker(team: TeamState, flag_y: float) -> PlayerState:
    """Pick the named taker for that side still on the pitch, else the best deliverer."""
    named = team.sheet.corner_takers.left if flag_y < CENTRE else team.sheet.corner_takers.right
    for player in team.players:
        if player.player_id == named:
            return player
    outfield = [player for player in team.players if player is not team.keeper]
    return max(outfield, key=lambda player: (player.skills.set_piece_delivery, -player.slot))


def attacking_strength(player: PlayerState) -> float:
    """Aerial threat of an attacker: heading, reach and movement (1-100)."""
    skills = player.skills
    return 0.5 * skills.heading + 0.3 * skills.jumping_reach + 0.2 * skills.off_ball_movement


def defending_strength(player: PlayerState) -> float:
    """Aerial defence of a defender: heading, marking and positioning (1-100)."""
    skills = player.skills
    return 0.4 * skills.heading + 0.3 * skills.marking + 0.3 * skills.positioning


def build_duel(play: Play, side: Side, taker: PlayerState) -> Duel:
    """Pick the men in the box and compute the attackers' share, lifted by the delivery."""
    state, cfg = play.state, play.cfg.restarts
    team, other = state.team(side), state.team(opposite(side))
    pool = [p for p in team.players if p is not team.keeper and p is not taker]
    pool.sort(key=lambda p: (-attacking_strength(p), p.slot))
    attackers = pool[: team.view.corner_attackers]
    outfield = [p for p in other.players if p is not other.keeper]
    outfield.sort(key=lambda p: (-defending_strength(p), p.slot))
    defenders = outfield[:DEFENDERS_IN_BOX]
    if not attackers or not defenders:
        return Duel(attackers, defenders, 0.0)
    attack = sum(attacking_strength(p) for p in attackers) / len(attackers)
    defence = sum(defending_strength(p) for p in defenders) / len(defenders)
    quality = squash((taker.skills.set_piece_delivery - DELIVERY_PIVOT) / DELIVERY_SCALE) - CENTRE
    lift = 1.0 + cfg.corner_delivery_swing * 2.0 * quality
    return Duel(attackers, defenders, clamp(attack / (attack + defence) * lift, 0.0, 1.0))


def header_xg(play: Play, shooter: PlayerState, share: float) -> float:
    """Return the quality of a header from a corner: base x (0.6 + 0.8 share) x heading factor."""
    base = play.cfg.restarts.corner_xg_base
    return base * (0.6 + 0.8 * share) * (0.8 + 0.4 * shooter.skills.heading / PERCENT)


def _header(play: Play, duel: Duel, taker: PlayerState) -> float:
    """An attacker meets the ball: he becomes the carrier and shoots (the normal shot model)."""
    state = play.state
    weights = [p.skills.heading for p in duel.attackers]
    shooter = duel.attackers[play.setpiece.choice_weighted(weights)]
    direction = state.team(shooter.side).attack_dir
    spot = (frame_coordinate(HEADER_FRAME_X, direction), shooter.y)
    take_possession(state, shooter, spot[0], spot[1])
    state.assist_from = taker
    goal = (frame_coordinate(1.0, direction), frame_coordinate(CENTRE, direction))
    xg = header_xg(play, shooter, duel.share)
    option = Option(ActionKind.SHOOT, 0.0, xg, goal, HEADER_PRESSURE, xg=xg, header=True)
    # Lazy import breaks the cycle shot -> out_of_play -> corner -> shot.
    from footystreams.sim.actions.resolve_shot import resolve_shot  # noqa: PLC0415

    return resolve_shot(play, option)


def _clearance(play: Play, duel: Duel, side: Side) -> None:
    """The defence heads it away; either side may win the second ball."""
    state = play.state
    header = duel.defenders[0]
    spot = (header.x, header.y)
    meta = Meta(team=header.side, participants=(actor(header, "actor"),), pos=spot)
    play.emit.emit(state, ClearanceEvent, meta, player_id=header.player_id)
    direction = state.team(side).attack_dir
    landing = (frame_coordinate(CLEARANCE_FRAME_X, direction), frame_coordinate(CENTRE, direction))
    attackers_win = play.setpiece.u() < SECOND_BALL_ATTACKER_SHARE
    winner_team = state.team(side if attackers_win else opposite(side))
    take_possession(state, nearest_outfielder(winner_team, landing), landing[0], landing[1])


def _keeper_claims(play: Play, side: Side) -> None:
    state = play.state
    defenders = state.team(opposite(side))
    spot = (frame_coordinate(GOAL_KICK_FRAME_X, defenders.attack_dir), CENTRE)
    take_possession(state, defenders.keeper, spot[0], spot[1])


def deliver(play: Play, side: Side, taker: PlayerState) -> float:
    """Play the ball into the box and resolve the aerial duel; return the extra seconds.

    One `setpiece` draw picks the branch: the keeper claims, an attacker heads at goal, or the
    defence clears. Shared by corners and crossed free kicks.
    """
    cfg = play.cfg.restarts
    duel = build_duel(play, side, taker)
    roll = play.setpiece.u()
    claim = cfg.corner_keeper_claim * (CLAIM_BASE - duel.share)
    if not duel.attackers or roll < claim:
        _keeper_claims(play, side)
        return 0.0
    if roll < claim + cfg.corner_shot_share * duel.share:
        return _header(play, duel, taker)
    _clearance(play, duel, side)
    return 0.0


def corner(play: Play, side: Side, flag: Point) -> float:
    """Take a corner for `side` from the flag at `flag`; return the stoppage seconds."""
    state, cfg = play.state, play.cfg.restarts
    taker = choose_corner_taker(state.team(side), flag[1])
    meta = Meta(team=side, participants=(actor(taker, "taker"),), pos=flag)
    play.emit.emit(
        state,
        CornerEvent,
        meta,
        taker_id=taker.player_id,
        side="left" if flag[1] < CENTRE else "right",
    )
    take_possession(state, taker, flag[0], flag[1])
    seconds = restart_delay(play, cfg.corner_s, cfg.corner_spread_s)
    taking = state.team(side)
    flag_frame = (
        frame_coordinate(flag[0], taking.attack_dir),
        frame_coordinate(flag[1], taking.attack_dir),
    )
    layout = corner_layout(state, taking, taker, flag_frame, taking.view.corner_attackers)
    settle(play, taking, layout, seconds, keyframe=True)
    return seconds + deliver(play, side, taker)
