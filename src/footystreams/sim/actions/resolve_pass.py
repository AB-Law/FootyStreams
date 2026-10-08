"""Resolve a pass: completion, interception, a lost loose ball, or out of play."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from footystreams.events.open_play import PassEvent
from footystreams.sim.actions.challenge import (
    nearest_defender_to,
    pick_interceptor,
    record_interception,
)
from footystreams.sim.actions.passing import PassKind
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import Point
from footystreams.sim.mathx import clamp
from footystreams.sim.options import Option
from footystreams.sim.play import Play, action_duration, actor, take_possession
from footystreams.sim.state import PlayerState

_LONG_KINDS = (PassKind.LONG, PassKind.CROSS)
FailedOutcome = Literal["intercepted", "incomplete", "out"]


@dataclass(frozen=True, slots=True)
class Failure:
    """How a pass failed and which defender comes away with the ball."""

    outcome: FailedOutcome
    winner: PlayerState


def failure_split(play: Play, option: Option) -> tuple[float, float]:
    """Return the cumulative shares (intercepted, intercepted + loose) of a failed pass.

    Long balls and crosses are likelier to go out of play than short passes.
    """
    cfg = play.cfg.challenge
    shift = cfg.fail_out_long_shift if option.pass_kind in _LONG_KINDS else 0.0
    intercept = max(0.0, cfg.fail_intercept - shift)
    return intercept, intercept + cfg.fail_loose


def _inside_pitch(point: Point) -> Point:
    return clamp(point[0], 0.0, 1.0), clamp(point[1], 0.0, 1.0)


def _fail(play: Play, option: Option, start: Point) -> Failure:
    """Decide how a failed pass fails (one draw, plus one to pick an interceptor)."""
    intercepted_below, loose_below = failure_split(play, option)
    roll = play.rng.u()
    if roll < intercepted_below:
        return Failure("intercepted", pick_interceptor(play, start, option.end))
    if roll < loose_below:
        return Failure("incomplete", nearest_defender_to(play, option.end))
    return Failure("out", nearest_defender_to(play, _inside_pitch(option.end)))


def resolve_pass(play: Play, option: Option) -> float:
    """Play out the chosen pass and return how many seconds it took."""
    state = play.state
    passer, receiver = state.carrier, option.target
    if receiver is None:
        msg = "a pass option needs a target"
        raise ValueError(msg)
    start: Point = (passer.x, passer.y)
    failure = None if play.rng.u() < option.probability else _fail(play, option, start)
    meta = Meta(
        team=passer.side,
        participants=(actor(passer, "actor"), actor(receiver, "target")),
        pos=start,
    )
    pass_id = play.emit.emit(
        state,
        PassEvent,
        meta,
        from_player_id=passer.player_id,
        to_player_id=receiver.player_id,
        outcome="complete" if failure is None else failure.outcome,
        length_m=round(option.length_m, 1),
    )
    if failure is None:
        take_possession(state, receiver, option.end[0], option.end[1])
        state.assist_from = passer
    elif failure.outcome == "intercepted":
        record_interception(play, failure.winner, pass_id)
    else:
        spot = _inside_pitch(option.end)
        take_possession(state, failure.winner, spot[0], spot[1])
    tempo = play.cfg.tempo
    return action_duration(play, tempo.pass_base_s + tempo.pass_per_m_s * option.length_m)
