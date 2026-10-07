"""The AI manager's candidate actions and how one is chosen (docs/design/02 section 11).

Each candidate carries a weight built from the manager's habits (fresh-legs, chase-the-game,
protect-the-lead and card-reaction biases) and the assessment. "Do nothing" has a prior weight, so
a calm match is left alone; one candidate or nothing is drawn per checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.manager import SubHabits
from footystreams.sim.config_manager import ManagerConfig
from footystreams.sim.manager_assess import Assessment
from footystreams.sim.rng import SimRng
from footystreams.sim.state import PlayerState

MAX_MARGIN = 2  # a third goal of lead or deficit adds no urgency


@dataclass(frozen=True, slots=True)
class Plan:
    """One thing the manager may do: an optional change of player and a shift of mentality."""

    reason: str
    weight: float
    off: PlayerState | None = None
    rungs: int = 0  # mentality steps (positive = more attacking)


def _fresh_legs(view: Assessment, habits: SubHabits, cfg: ManagerConfig) -> Plan | None:
    if view.minute < habits.earliest_minute or not view.tired:
        return None
    apparent, player = view.tired[0]
    excess = apparent - cfg.fatigue_threshold
    if excess <= 0.0:
        return None
    weight = habits.fresh_legs_bias * cfg.fatigue_gain * excess * (0.5 + habits.aggressiveness)
    return Plan("fresh_legs", weight, off=player)


def _chase_or_protect(view: Assessment, habits: SubHabits, cfg: ManagerConfig) -> Plan | None:
    urgency = min(abs(view.margin), MAX_MARGIN)
    if view.margin < 0 and view.minute >= cfg.chase_from_min:
        weight = habits.chase_game_bias * cfg.tactical_gain * urgency
        return Plan("chase_game", weight, view.tired[0][1] if view.tired else None, rungs=1)
    if view.margin > 0 and view.minute >= cfg.protect_from_min:
        weight = habits.protect_lead_bias * cfg.tactical_gain * urgency
        return Plan("protect_lead", weight, view.tired[0][1] if view.tired else None, rungs=-1)
    return None


def _after_dismissal(view: Assessment, seen_difference: int, cfg: ManagerConfig) -> Plan | None:
    """React once to a change in the number of men: sit tighter a man down, push a man up."""
    if view.men_difference in (seen_difference, 0):
        return None
    if view.men_difference > 0:
        return Plan("opponent_dismissal", cfg.card_gain, rungs=1)
    return Plan("dismissal", cfg.card_gain, rungs=0 if view.margin < 0 else -1)


def _yellow_risk(view: Assessment, habits: SubHabits, cfg: ManagerConfig) -> Plan | None:
    in_window = cfg.yellow_from_min <= view.minute <= cfg.yellow_until_min
    if not in_window or not view.booked:
        return None
    risky = view.booked[0]
    if risky.skills.aggression < cfg.yellow_aggression:
        return None
    return Plan("yellow_risk", habits.reacts_to_cards * cfg.yellow_gain, off=risky)


def candidate_plans(
    view: Assessment, habits: SubHabits, seen_difference: int, cfg: ManagerConfig
) -> list[Plan]:
    """Return the actions open to the manager now, each with a positive weight."""
    found = (
        _fresh_legs(view, habits, cfg),
        _chase_or_protect(view, habits, cfg),
        _after_dismissal(view, seen_difference, cfg),
        _yellow_risk(view, habits, cfg),
    )
    return [plan for plan in found if plan is not None and plan.weight > 0.0]


def choose_plan(plans: list[Plan], rng: SimRng, cfg: ManagerConfig) -> Plan | None:
    """Draw one plan, or None for "do nothing" (consumes one draw when there is a plan)."""
    if not plans:
        return None
    pick = rng.choice_weighted([cfg.stay_weight, *(plan.weight for plan in plans)])
    return None if pick == 0 else plans[pick - 1]
