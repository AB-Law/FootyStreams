"""Resolve a pass: completion, interception, a lost loose ball, or out of play."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from footystreams.events.open_play import PassEvent
from footystreams.sim.actions.challenge import pick_interceptor, record_interception
from footystreams.sim.actions.nearest import nearest_defender_to
from footystreams.sim.actions.offside import offside_called, punish_offside
from footystreams.sim.actions.out_of_play import out_of_play
from footystreams.sim.actions.passing import PassKind
from footystreams.sim.actions.restarts import left_pitch, overhit_point
from footystreams.sim.emit import Meta
from footystreams.sim.enrich import pass_fields
from footystreams.sim.geometry import Point, frame_coordinate
from footystreams.sim.mathx import clamp
from footystreams.sim.options import Option
from footystreams.sim.play import Play, action_duration, actor, take_possession
from footystreams.sim.side import opposite
from footystreams.sim.state import PlayerState

_LONG_KINDS = (PassKind.LONG, PassKind.CROSS)
FailedOutcome = Literal["intercepted", "incomplete", "out"]


@dataclass(frozen=True, slots=True)
class Failure:
    """How a pass failed and which defender comes away with the ball.

    `exit_point` is set only for a pass that left the pitch (and then `winner` is a placeholder
    for the restart's taker).
    """

    outcome: FailedOutcome
    winner: PlayerState
    exit_point: Point | None = None
    deflected: bool = False  # a defender touched it last on its way out


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
        blocker = pick_interceptor(play, start, option.end)
        if option.pass_kind is PassKind.CROSS and _blocked_behind(play):
            behind = (frame_coordinate(1.0, state_dir(play)), option.end[1])
            return Failure("out", blocker, behind, deflected=True)
        return Failure("intercepted", blocker)
    if roll < loose_below:
        return Failure("incomplete", nearest_defender_to(play, option.end))
    return _overhit(play, option, start)


def state_dir(play: Play) -> int:
    """Return the attack direction of the side in possession."""
    return play.state.attackers.attack_dir


def _blocked_behind(play: Play) -> bool:
    """True when restarts are on and a blocked cross is deflected behind (one `setpiece` draw)."""
    cfg = play.cfg.restarts
    return cfg.enabled and play.setpiece.u() < cfg.cross_corner_share


def _overhit(play: Play, option: Option, start: Point) -> Failure:
    """An overhit pass: out of play if it leaves the pitch (restarts enabled), else a loose ball."""
    cfg = play.cfg.restarts
    if not cfg.enabled:
        return Failure("out", nearest_defender_to(play, _inside_pitch(option.end)))
    extra = cfg.overhit_min_m + (cfg.overhit_max_m - cfg.overhit_min_m) * play.rng.u()
    landing = overhit_point(start, option.end, extra)
    winner = nearest_defender_to(play, _inside_pitch(landing))
    if left_pitch(landing):
        return Failure("out", winner, landing)
    return Failure("incomplete", winner)


def _receive(
    play: Play, passer: PlayerState, receiver: PlayerState, option: Option, pass_id: str
) -> float:
    """The receiver gets the ball, unless the referee flags him offside; return extra seconds."""
    if play.cfg.offside.enabled and offside_called(play, passer, receiver):
        return punish_offside(play, receiver, pass_id)
    take_possession(play.state, receiver, option.end[0], option.end[1])
    play.state.assist_from = passer
    return 0.0


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
        **pass_fields(play, start, option),
    )
    tempo = play.cfg.tempo
    duration = action_duration(play, tempo.pass_base_s + tempo.pass_per_m_s * option.length_m)
    if failure is None:
        return duration + _receive(play, passer, receiver, option, pass_id)
    if failure.exit_point is not None:
        touch = opposite(passer.side) if failure.deflected else passer.side
        return duration + out_of_play(play, failure.exit_point, touch)
    if failure.outcome == "intercepted":
        record_interception(play, failure.winner, pass_id)
    else:
        spot = _inside_pitch(option.end)
        take_possession(state, failure.winner, spot[0], spot[1])
    return duration
