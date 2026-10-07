"""Challenges for the ball: tackles on the carrier, interceptions and loose-ball pick-ups."""

from __future__ import annotations

from footystreams.events.open_play import InterceptionEvent, TackleEvent
from footystreams.sim.actions.dribbling import defending_rating, dribbling_rating
from footystreams.sim.actions.foul import contest_foul
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import Point, segment_distance_m
from footystreams.sim.mathx import squash
from footystreams.sim.play import Play, action_duration, actor, take_possession
from footystreams.sim.pressure import nearest_opponents
from footystreams.sim.state import PlayerState

_INTERCEPTOR_CANDIDATES = 3


def tackle_win_probability(tackler: PlayerState, carrier: PlayerState, play: Play) -> float:
    """Return the chance a tackle takes the ball: defending rating against the carrier's rating."""
    cfg = play.cfg.challenge
    edge = (defending_rating(tackler.skills) - dribbling_rating(carrier.skills)) / cfg.tackle_scale
    return cfg.tackle_base + cfg.tackle_swing * (squash(edge) - 0.5) * 2.0


def attempt_press_tackle(play: Play, pressure: float) -> float | None:
    """Let the nearest defender challenge the carrier.

    Returns the seconds the moment took when the challenge ended it (a won tackle or a foul), or
    None when play carries on (no challenge, or a missed one, emitted as a `tackle` with outcome
    `missed`). Consumes one draw to decide whether a challenge happens, then the foul draws, then
    one to resolve it.
    """
    state, cfg = play.state, play.cfg.challenge
    carrier = state.carrier
    gap, tackler = nearest_opponents(state.defenders, carrier.x, carrier.y, 1)[0]
    if play.rng.u() >= cfg.attempt_rate * pressure or gap > cfg.attempt_radius_m:
        return None
    stoppage = contest_foul(play, tackler, carrier, None)
    if stoppage is not None:
        return stoppage + action_duration(play, play.cfg.tempo.tackle_s)
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
    if not won:
        return None
    take_possession(state, tackler, carrier.x, carrier.y)
    return action_duration(play, play.cfg.tempo.tackle_s)


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
