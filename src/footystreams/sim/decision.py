"""The decision model: weigh the carrier's options and pick one (docs/design/02 section 5.2).

Selection is a softmax built from rational weights (no exp): good decision-makers choose close to
the best option, stressed or poor ones scatter. Exactly one random draw is consumed per decision.
"""

from __future__ import annotations

from footystreams.sim.config import SimConfig
from footystreams.sim.geometry import CENTRE
from footystreams.sim.mathx import PERCENT, clamp, rational_weight
from footystreams.sim.options import Option, Weights, generate_options
from footystreams.sim.rng import SimRng
from footystreams.sim.state import REGULATION_PERIOD_S, MatchState

REGULATION_S = 2 * REGULATION_PERIOD_S
LATE_START_S = 3000.0  # urgency starts to build around the 50th minute
_TEMPERATURE_DECISION_PIVOT = 1.3
_MAX_MARGIN = 2.0
_KEEP_URGENCY = 0.2
_RISK_SWING = 0.3
_MIN_TEMPERATURE = 1e-6  # guards the division in the softmax; never reached with a valid config


def urgency(state: MatchState) -> float:
    """Return how badly the possessing team needs a goal: -1 (protect lead) .. +1 (chase game).

    Grows with the deficit (capped at two goals) and with how late it is.
    """
    team = state.attackers
    margin = clamp(float(state.defenders.score - team.score), -_MAX_MARGIN, _MAX_MARGIN)
    lateness = clamp((state.elapsed_s - LATE_START_S) / (REGULATION_S - LATE_START_S), 0.0, 1.0)
    return clamp(margin / _MAX_MARGIN, -1.0, 1.0) * lateness


def team_weights(state: MatchState, cfg: SimConfig) -> Weights:
    """Return the utility weights for the possessing team from tactics and game state."""
    view = state.attackers.view
    push = urgency(state)
    decision = cfg.decision
    progress = (
        1.0
        + decision.mentality_swing * view.mentality
        + (view.directness - CENTRE) * decision.directness_bias
        + decision.urgency_swing * push
    )
    keep = 1.0 - _KEEP_URGENCY * push + (view.patience - CENTRE) * decision.directness_bias
    risk = 1.0 - _RISK_SWING * (view.risk_taking - CENTRE) * 2.0
    floor = decision.min_utility_weight
    return Weights(max(floor, progress), max(floor, keep), max(floor, risk))


def choice_temperature(decisions: float, pressure: float, cfg: SimConfig) -> float:
    """Return the softmax temperature: base x (1.3 - decisions/100) x (1 + k x pressure) x scale."""
    decision = cfg.decision
    calm = decision.temperature_base * (_TEMPERATURE_DECISION_PIVOT - decisions / PERCENT)
    return calm * (1.0 + decision.temperature_pressure * pressure) * decision.temperature_scale


def choose(options: list[Option], decisions: float, rng: SimRng, cfg: SimConfig) -> Option:
    """Pick one option by softmax over utility; consumes one draw."""
    pressure = options[0].pressure
    temperature = max(_MIN_TEMPERATURE, choice_temperature(decisions, pressure, cfg))
    best = max(option.utility for option in options)
    weights = [
        rational_weight(option.utility, best, 1.0 / temperature, cfg.decision.weight_floor)
        for option in options
    ]
    return options[rng.choice_weighted(weights)]


def decide(state: MatchState, rng: SimRng, cfg: SimConfig, pressure: float) -> Option:
    """Build the carrier's options under the given pressure and choose what he does."""
    options = generate_options(state, pressure, team_weights(state, cfg), cfg)
    return choose(options, state.carrier.skills.decisions, rng, cfg)
