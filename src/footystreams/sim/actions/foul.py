"""A called foul on the pitch: the tackle, the foul, advantage or the free kick."""

from __future__ import annotations

from footystreams.events.discipline import FoulEvent
from footystreams.events.open_play import TackleEvent
from footystreams.sim.actions.setpieces import take_free_kick
from footystreams.sim.discipline import Contact, roll_contact
from footystreams.sim.emit import Meta
from footystreams.sim.play import Play, actor, label
from footystreams.sim.state import PlayerState

_ADVANTAGE_BLOCKED_BY = "violent"  # a violent foul is always whistled


def plays_advantage(play: Play, contact: Contact) -> bool:
    """Decide whether the referee waves play on (one `discipline` draw).

    Never in the penalty area or after a violent foul; otherwise the chance is the referee's
    advantage tendency scaled by the config.
    """
    if contact.in_box or contact.label == _ADVANTAGE_BLOCKED_BY:
        return False
    chance = play.cfg.discipline.advantage_scale * play.referee.advantage_tendency
    return play.discipline.u() < chance


def contest_foul(
    play: Play, tackler: PlayerState, carrier: PlayerState, caused_by: str | None
) -> float | None:
    """Roll for a called foul in a challenge; return the stoppage seconds, or None if none.

    On a called foul this emits the tackle (outcome `foul`) and the foul, then either lets
    advantage run (no restart; the fouled side keeps the ball) or restarts with a free kick.
    """
    contact = roll_contact(play, tackler, carrier)
    if contact is None:
        return None
    state = play.state
    spot = (carrier.x, carrier.y)
    tackle_id = play.emit.emit(
        state,
        TackleEvent,
        Meta(
            team=tackler.side,
            participants=(actor(tackler, "tackler"), actor(carrier, "fouled")),
            pos=spot,
            caused_by=caused_by,
        ),
        player_id=tackler.player_id,
        target_id=carrier.player_id,
        outcome="foul",
    )
    foul_id = play.emit.emit(
        state,
        FoulEvent,
        Meta(
            team=tackler.side,
            participants=(actor(tackler, "fouler"), actor(carrier, "fouled")),
            pos=spot,
            caused_by=tackle_id,
            headline=f"Foul by {label(state.team(tackler.side), tackler.player_id)}",
        ),
        fouler_id=tackler.player_id,
        fouled_id=carrier.player_id,
        severity=contact.label,
    )
    if plays_advantage(play, contact):
        return 0.0
    return take_free_kick(play, carrier.side, spot, "direct", foul_id)
