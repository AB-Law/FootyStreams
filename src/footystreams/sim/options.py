"""The carrier's options: what he could do right now and how good each looks.

Candidates are passes to the most promising teammates (plus one safe outlet), a dribble, a shot
when in range and a clearance when harried near his own goal (docs/design/02 section 5.2). Each
option carries its success probability and utility; `decision.py` picks one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from footystreams.sim.actions.dribbling import dribble_success_probability
from footystreams.sim.actions.passing import (
    PassAttempt,
    PassKind,
    classify_pass,
    pass_skill,
    pass_success_probability,
)
from footystreams.sim.actions.shooting import shot_chance
from footystreams.sim.config import SimConfig
from footystreams.sim.geometry import (
    CENTRE,
    PITCH_LENGTH_M,
    Point,
    distance_m,
    frame_coordinate,
    goal_distance_m,
)
from footystreams.sim.mathx import clamp
from footystreams.sim.pressure import nearest_opponents, openness
from footystreams.sim.state import Line, MatchState, PlayerState
from footystreams.sim.threat import threat

_FORWARD_WEIGHT = 1.0
_LENGTH_WEIGHT = 0.012  # per metre when ranking candidate receivers
_KEEPER_PENALTY = 0.6
_PERCENT = 100.0
_DRIBBLE_CENTRING = 0.3  # share of the way toward the centre line a dribble drifts
_CLEARANCE_DISTANCE = 0.35  # frame-x a clearance travels
_CLEARANCE_MAX_FRAME_X = 0.8
_MAX_FRAME_X = 0.99


class ActionKind(StrEnum):
    """What the carrier does."""

    PASS = "pass"  # noqa: S105 - a football pass, not a password
    DRIBBLE = "dribble"
    SHOOT = "shoot"
    CLEAR = "clear"


@dataclass(slots=True)
class Weights:
    """Game-state dependent utility weights for the carrier's team."""

    progress: float
    keep: float
    risk: float


@dataclass(slots=True)
class Option:
    """One thing the carrier could do, with its odds and appeal."""

    kind: ActionKind
    utility: float
    probability: float
    end: Point  # absolute coordinates
    pressure: float
    target: PlayerState | None = None
    pass_kind: PassKind | None = None
    length_m: float = 0.0
    xg: float = 0.0


@dataclass(frozen=True, slots=True)
class Situation:
    """Everything an option needs, computed once per decision: state, frame, pressure, weights."""

    state: MatchState
    cfg: SimConfig
    weights: Weights
    pressure: float
    direction: int
    fx: float  # carrier position in his team's frame
    fy: float

    @property
    def carrier(self) -> PlayerState:
        """The player on the ball."""
        return self.state.carrier


def situation_of(state: MatchState, pressure: float, weights: Weights, cfg: SimConfig) -> Situation:
    """Build the situation for the current carrier."""
    direction = state.attackers.attack_dir
    carrier = state.carrier
    return Situation(
        state,
        cfg,
        weights,
        pressure,
        direction,
        frame_coordinate(carrier.x, direction),
        frame_coordinate(carrier.y, direction),
    )


def loss_cost(frame_x: float, cfg: SimConfig) -> float:
    """Return how costly losing the ball here is: highest at the own goal line."""
    behind = 1.0 - frame_x
    return cfg.decision.loss_cost_base + cfg.decision.loss_cost_own_third * behind * behind


def _utility(situation: Situation, gain: float, probability: float, bias: float) -> float:
    """Combine progression, keeping the ball, risk of losing it and a style bias."""
    weights, cfg = situation.weights, situation.cfg
    return (
        weights.progress * cfg.decision.progress_scale * gain
        + weights.keep * probability
        - weights.risk * (1.0 - probability) * loss_cost(situation.fx, cfg)
        + bias
    )


def _kind_bias(kind: PassKind, situation: Situation) -> float:
    view = situation.state.attackers.view
    decision = situation.cfg.decision
    if kind in (PassKind.LONG, PassKind.THROUGH):
        return (view.directness - CENTRE) * decision.directness_bias
    if kind is PassKind.CROSS:
        return (view.crossing_frequency - CENTRE) * decision.cross_bias
    if kind is PassKind.BACK:
        recycle = (view.patience - CENTRE) + situation.pressure
        return recycle * decision.recycle_bias
    return 0.0


def _pass_option(situation: Situation, mate: PlayerState) -> Option | None:
    state, cfg, direction = situation.state, situation.cfg, situation.direction
    carrier = state.carrier
    end_fx = min(frame_coordinate(mate.x, direction) + cfg.decision.lead_frame_x, _MAX_FRAME_X)
    end_fy = frame_coordinate(mate.y, direction)
    end = (frame_coordinate(end_fx, direction), frame_coordinate(end_fy, direction))
    length = distance_m(carrier.x, carrier.y, end[0], end[1])
    if length < cfg.decision.min_pass_m:
        return None
    kind = classify_pass((situation.fx, situation.fy), (end_fx, end_fy), length, cfg.passing)
    attempt = PassAttempt(
        kind=kind,
        length_m=length,
        skill=pass_skill(kind, carrier.skills),
        receiver_touch=mate.skills.first_touch,
        pressure=situation.pressure,
        openness=openness(carrier, end[0], end[1], state.defenders, cfg.pressure),
    )
    probability = pass_success_probability(attempt, cfg.passing)
    gain = threat(end_fx, end_fy) - threat(situation.fx, situation.fy)
    utility = _utility(situation, gain, probability, _kind_bias(kind, situation))
    return Option(
        ActionKind.PASS, utility, probability, end, situation.pressure, mate, kind, length
    )


def _candidate_mates(situation: Situation) -> list[PlayerState]:
    state, cfg, direction = situation.state, situation.cfg, situation.direction
    carrier = state.carrier

    def appeal(mate: PlayerState) -> float:
        forward = frame_coordinate(mate.x, direction) - situation.fx
        penalty = _KEEPER_PENALTY if mate.line is Line.KEEPER else 0.0
        reach = distance_m(carrier.x, carrier.y, mate.x, mate.y)
        return _FORWARD_WEIGHT * forward - _LENGTH_WEIGHT * reach - penalty

    mates = sorted(
        (mate for mate in state.attackers.players if mate is not carrier),
        key=lambda mate: (-appeal(mate), mate.slot),
    )
    chosen = mates[: cfg.decision.candidates]
    outlet = min(
        (mate for mate in mates[cfg.decision.candidates :] if mate.line is not Line.KEEPER),
        key=lambda mate: distance_m(carrier.x, carrier.y, mate.x, mate.y),
        default=None,
    )
    return [*chosen, outlet] if outlet is not None else chosen


def _dribble_option(situation: Situation) -> Option:
    state, cfg, direction = situation.state, situation.cfg, situation.direction
    carrier = state.carrier
    step = cfg.dribble.distance_m / PITCH_LENGTH_M
    end_fx = min(situation.fx + step, _MAX_FRAME_X)
    end_fy = clamp(situation.fy + (CENTRE - situation.fy) * _DRIBBLE_CENTRING, 0.0, 1.0)
    end = (frame_coordinate(end_fx, direction), frame_coordinate(end_fy, direction))
    nearest = nearest_opponents(state.defenders, end[0], end[1], 1)
    defender = nearest[0][1].skills if nearest else None
    probability = dribble_success_probability(
        carrier.skills, defender, situation.pressure, cfg.dribble
    )
    gain = threat(end_fx, end_fy) - threat(situation.fx, situation.fy)
    view = state.attackers.view
    bias = (view.dribbling_freedom - CENTRE) * cfg.decision.dribble_bias
    bias += (carrier.skills.flair / _PERCENT - CENTRE) * cfg.decision.dribble_bias
    utility = _utility(situation, gain, probability, bias)
    return Option(ActionKind.DRIBBLE, utility, probability, end, situation.pressure)


def _shot_option(situation: Situation) -> Option | None:
    state, cfg = situation.state, situation.cfg
    if goal_distance_m(situation.fx, situation.fy) > cfg.shot.range_m:
        return None
    chance = shot_chance(
        (situation.fx, situation.fy), state.carrier.skills, situation.pressure, cfg.shot
    )
    if chance.xg < cfg.shot.min_xg:
        return None
    view = state.attackers.view
    appetite = 1.0 + cfg.decision.shoot_on_sight_swing * (view.shoot_on_sight - CENTRE) * 2.0
    utility = cfg.decision.shot_scale * chance.xg * appetite
    goal = (
        frame_coordinate(1.0, situation.direction),
        frame_coordinate(CENTRE, situation.direction),
    )
    return Option(ActionKind.SHOOT, utility, chance.xg, goal, situation.pressure, xg=chance.xg)


def _clear_option(situation: Situation) -> Option | None:
    decision = situation.cfg.decision
    if situation.pressure < decision.clear_pressure or situation.fx > decision.clear_max_frame_x:
        return None
    utility = decision.clear_base + decision.clear_slope * (
        situation.pressure - decision.clear_pressure
    )
    target_fx = min(situation.fx + _CLEARANCE_DISTANCE, _CLEARANCE_MAX_FRAME_X)
    end = (frame_coordinate(target_fx, situation.direction), situation.state.carrier.y)
    return Option(ActionKind.CLEAR, utility, 1.0 - situation.pressure, end, situation.pressure)


def generate_options(
    state: MatchState, pressure: float, weights: Weights, cfg: SimConfig
) -> list[Option]:
    """Return every option open to the current carrier (never empty)."""
    situation = situation_of(state, pressure, weights, cfg)
    options: list[Option] = []
    for mate in _candidate_mates(situation):
        passing = _pass_option(situation, mate)
        if passing is not None:
            options.append(passing)
    options.append(_dribble_option(situation))
    optional = (_shot_option(situation), _clear_option(situation))
    options.extend(option for option in optional if option is not None)
    return options
