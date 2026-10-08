"""Challenges for the ball: tackles on the carrier, interceptions and loose-ball pick-ups."""

from __future__ import annotations

from footystreams.events.open_play import InterceptionEvent, TackleEvent
from footystreams.sim.actions.dribbling import defending_rating, dribbling_rating
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import Point, distance_m, segment_distance_m
from footystreams.sim.mathx import signed_unit, squash
from footystreams.sim.play import Play, actor, take_possession
from footystreams.sim.pressure import nearest_opponents
from footystreams.sim.state import PlayerState

_INTERCEPTOR_CANDIDATES = 3


def tackle_win_probability(tackler: PlayerState, carrier: PlayerState, play: Play) -> float:
    """Return the chance a tackle takes the ball: defending rating against the carrier's rating."""
    cfg = play.cfg.challenge
    edge = (defending_rating(tackler.skills) - dribbling_rating(carrier.skills)) / cfg.tackle_scale
    return cfg.tackle_base + cfg.tackle_swing * signed_unit(squash(edge))


def attempt_press_tackle(play: Play, pressure: float) -> bool:
    """Let the nearest defender try to dispossess the carrier; True when the ball changed hands.

    Consumes one draw to decide whether a challenge happens and one more to resolve it. A missed
    challenge is emitted as a `tackle` with outcome `missed` and play carries on.
    """
    state, cfg = play.state, play.cfg.challenge
    nearest = nearest_opponents(state.defenders, state.carrier.x, state.carrier.y, 1)
    gap, tackler = nearest[0]
    if play.rng.u() >= cfg.attempt_rate * pressure or gap > cfg.attempt_radius_m:
        return False
    carrier = state.carrier
    won = play.rng.u() < tackle_win_probability(tackler, carrier, play)
    meta = Meta(
        team=tackler.side,
        participants=(actor(tackler, "tackler"), actor(carrier, "carrier")),
        pos=(carrier.x, carrier.y),
    )
    play.emit.emit(
        state,
        TackleEvent,
        meta,
        player_id=tackler.player_id,
        target_id=carrier.player_id,
        outcome="won" if won else "missed",
    )
    if won:
        take_possession(state, tackler, carrier.x, carrier.y)
    return won


def pick_interceptor(play: Play, start: Point, end: Point) -> PlayerState:
    """Choose which defender cuts out a pass, weighted by closeness to the lane and reading."""
    defenders = sorted(
        play.state.defenders.players,
        key=lambda player: (segment_distance_m((player.x, player.y), start, end), player.slot),
    )[:_INTERCEPTOR_CANDIDATES]
    weights = [
        (player.skills.anticipation + player.skills.positioning)
        / (1.0 + segment_distance_m((player.x, player.y), start, end))
        for player in defenders
    ]
    return defenders[play.rng.choice_weighted(weights)]


def record_interception(play: Play, defender: PlayerState, pass_event_id: str) -> None:
    """Emit the interception caused by a failed pass and hand the ball to the defender."""
    state = play.state
    passer = state.carrier
    meta = Meta(
        team=defender.side,
        participants=(actor(defender, "actor"), actor(passer, "target")),
        pos=(defender.x, defender.y),
        caused_by=pass_event_id,
    )
    play.emit.emit(state, InterceptionEvent, meta, player_id=defender.player_id)
    take_possession(state, defender, defender.x, defender.y)


def nearest_defender_to(play: Play, point: Point) -> PlayerState:
    """Return the defender closest to a point (wins a loose ball there)."""
    return nearest_opponents(play.state.defenders, point[0], point[1], 1)[0][1]


def closest_of(players: list[PlayerState], point: Point) -> PlayerState:
    """Return the player nearest to a point; ties go to the lower slot."""
    return min(
        players,
        key=lambda player: (distance_m(point[0], point[1], player.x, player.y), player.slot),
    )
