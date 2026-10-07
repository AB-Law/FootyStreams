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


def loss_cost(frame_x: float, cfg: SimConfig) -> float:
    """Return how costly losing the ball here is: highest at the own goal line."""
    behind = 1.0 - frame_x
    return cfg.decision.loss_cost_base + cfg.decision.loss_cost_own_third * behind * behind


def _kind_bias(option_kind: PassKind, pressure: float, state: MatchState, cfg: SimConfig) -> float:
    view = state.attackers.view
    decision = cfg.decision
    if option_kind in (PassKind.LONG, PassKind.THROUGH):
        return (view.directness - CENTRE) * decision.directness_bias
    if option_kind is PassKind.CROSS:
        return (view.crossing_frequency - CENTRE) * decision.cross_bias
    if option_kind is PassKind.BACK:
        return (view.patience - CENTRE) * decision.recycle_bias + pressure * decision.recycle_bias
    return 0.0


def _pass_option(
    state: MatchState, mate: PlayerState, pressure: float, weights: Weights, cfg: SimConfig
) -> Option | None:
    carrier = state.carrier
    team = state.attackers
    direction = team.attack_dir
    lead = cfg.decision.lead_frame_x
    end_fx = min(frame_coordinate(mate.x, direction) + lead, 0.99)
    end_fy = frame_coordinate(mate.y, direction)
    end = (frame_coordinate(end_fx, direction), frame_coordinate(end_fy, direction))
    length = distance_m(carrier.x, carrier.y, end[0], end[1])
    if length < cfg.decision.min_pass_m:
        return None
    carrier_frame = (frame_coordinate(carrier.x, direction), frame_coordinate(carrier.y, direction))
    kind = classify_pass(carrier_frame, (end_fx, end_fy), length, cfg.passing)
    attempt = PassAttempt(
        kind=kind,
        length_m=length,
        skill=pass_skill(kind, carrier.skills),
        receiver_touch=mate.skills.first_touch,
        pressure=pressure,
        openness=openness(carrier, end[0], end[1], state.defenders, cfg.pressure),
    )
    probability = pass_success_probability(attempt, cfg.passing)
    gain = threat(end_fx, end_fy) - threat(*carrier_frame)
    utility = (
        weights.progress * cfg.decision.progress_scale * gain
        + weights.keep * probability
        - weights.risk * (1.0 - probability) * loss_cost(carrier_frame[0], cfg)
        + _kind_bias(kind, pressure, state, cfg)
    )
    return Option(ActionKind.PASS, utility, probability, end, pressure, mate, kind, length)


def _candidate_mates(state: MatchState, cfg: SimConfig) -> list[PlayerState]:
    carrier = state.carrier
    direction = state.attackers.attack_dir
    carrier_fx = frame_coordinate(carrier.x, direction)

    def appeal(mate: PlayerState) -> float:
        forward = frame_coordinate(mate.x, direction) - carrier_fx
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


def _dribble_option(state: MatchState, pressure: float, weights: Weights, cfg: SimConfig) -> Option:
    carrier = state.carrier
    direction = state.attackers.attack_dir
    fx = frame_coordinate(carrier.x, direction)
    fy = frame_coordinate(carrier.y, direction)
    step = cfg.dribble.distance_m / PITCH_LENGTH_M
    end_fx = min(fx + step, 0.99)
    end_fy = clamp(fy + (CENTRE - fy) * _DRIBBLE_CENTRING, 0.0, 1.0)
    end = (frame_coordinate(end_fx, direction), frame_coordinate(end_fy, direction))
    nearest = nearest_opponents(state.defenders, end[0], end[1], 1)
    defender = nearest[0][1].skills if nearest else None
    probability = dribble_success_probability(carrier.skills, defender, pressure, cfg.dribble)
    gain = threat(end_fx, end_fy) - threat(fx, fy)
    view = state.attackers.view
    bias = (view.dribbling_freedom - CENTRE) * cfg.decision.dribble_bias
    bias += (carrier.skills.flair / _PERCENT - CENTRE) * cfg.decision.dribble_bias
    utility = (
        weights.progress * cfg.decision.progress_scale * gain
        + weights.keep * probability
        - weights.risk * (1.0 - probability) * loss_cost(fx, cfg)
        + bias
    )
    return Option(ActionKind.DRIBBLE, utility, probability, end, pressure)


def _shot_option(state: MatchState, pressure: float, cfg: SimConfig) -> Option | None:
    carrier = state.carrier
    direction = state.attackers.attack_dir
    fx = frame_coordinate(carrier.x, direction)
    fy = frame_coordinate(carrier.y, direction)
    if goal_distance_m(fx, fy) > cfg.shot.range_m:
        return None
    chance = shot_chance((fx, fy), carrier.skills, pressure, cfg.shot)
    if chance.xg < cfg.shot.min_xg:
        return None
    view = state.attackers.view
    appetite = 1.0 + cfg.decision.shoot_on_sight_swing * (view.shoot_on_sight - CENTRE) * 2.0
    utility = cfg.decision.shot_scale * chance.xg * appetite
    goal = (frame_coordinate(1.0, direction), frame_coordinate(CENTRE, direction))
    return Option(ActionKind.SHOOT, utility, chance.xg, goal, pressure, xg=chance.xg)


def _clear_option(state: MatchState, pressure: float, cfg: SimConfig) -> Option | None:
    carrier = state.carrier
    direction = state.attackers.attack_dir
    fx = frame_coordinate(carrier.x, direction)
    decision = cfg.decision
    if pressure < decision.clear_pressure or fx > decision.clear_max_frame_x:
        return None
    utility = decision.clear_base + decision.clear_slope * (pressure - decision.clear_pressure)
    target_fx = min(fx + 0.35, 0.8)
    end = (frame_coordinate(target_fx, direction), carrier.y)
    return Option(ActionKind.CLEAR, utility, 1.0 - pressure, end, pressure)


def generate_options(
    state: MatchState, pressure: float, weights: Weights, cfg: SimConfig
) -> list[Option]:
    """Return every option open to the current carrier (never empty)."""
    options: list[Option] = []
    for mate in _candidate_mates(state, cfg):
        passing = _pass_option(state, mate, pressure, weights, cfg)
        if passing is not None:
            options.append(passing)
    options.append(_dribble_option(state, pressure, weights, cfg))
    optional = (_shot_option(state, pressure, cfg), _clear_option(state, pressure, cfg))
    options.extend(option for option in optional if option is not None)
    return options
