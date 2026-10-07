"""Modifiers created by rule from facts: what happened to a player in a match or on his return.

Deterministic and always on (docs/design/07 section 3.2). Each rule is small and named so it can
be read, tested and tuned on its own; thresholds and strengths live in ``mood.yaml``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.injury import Injury
from footystreams.domain.mood import ModifierSource, StateKind, StateModifier
from footystreams.domain.types import MatchId, PlayerId
from footystreams.league.modifiers import ModifierSpec, new_modifier
from footystreams.league.mood_config import MoodConfig
from footystreams.league.outcome import Outcome


@dataclass(frozen=True, slots=True)
class MatchFact:
    """What one player did in one match, as the rules need it."""

    player_id: PlayerId
    goals: int
    reds: int
    rating: float
    outcome: Outcome
    derby: bool


def _rules(fact: MatchFact, config: MoodConfig) -> list[tuple[StateKind, float]]:
    rules = config.rules
    earned: list[tuple[StateKind, float]] = []
    if fact.derby and fact.goals and fact.outcome is Outcome.WIN:
        earned.append((StateKind.DERBY_HERO, rules.derby_hero_magnitude))
    if fact.goals >= rules.confidence_goals or fact.rating >= rules.confidence_rating:
        earned.append((StateKind.CONFIDENCE_SURGE, rules.confidence_magnitude))
    if fact.reds and fact.outcome is Outcome.LOSS:
        earned.append((StateKind.BLAMED_FOR_DEFEAT, rules.blamed_magnitude))
    return earned


def modifiers_from_match(
    facts: Sequence[MatchFact], match_id: MatchId, today: dt.date, config: MoodConfig
) -> list[StateModifier]:
    """Derby heroes, confidence surges and blame for a match, in player order."""
    source = ModifierSource(origin="rule", match_id=match_id)
    return [
        new_modifier(ModifierSpec(kind, fact.player_id, magnitude, source), today, config)
        for fact in sorted(facts, key=lambda item: item.player_id)
        for kind, magnitude in _rules(fact, config)
    ]


def modifier_for_return(
    player_id: PlayerId, injury: Injury, today: dt.date, config: MoodConfig
) -> StateModifier | None:
    """The joy of coming back from a long injury; None for a short one."""
    days = (injury.expected_return_on - injury.started_on).days
    if days < config.rules.return_joy_min_days:
        return None
    source = ModifierSource(origin="rule")
    spec = ModifierSpec(
        StateKind.INJURY_RETURN_JOY, player_id, config.rules.return_joy_magnitude, source
    )
    return new_modifier(spec, today, config)
