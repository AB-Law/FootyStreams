"""Resolve a player's active state modifiers into the three frozen mood multipliers.

Pure and total: the same personality, date and modifiers always give the same ``ResolvedMood``,
and the result always sits inside the hard caps of ``MoodConfig`` (docs/design/07 section 3.3).

Each kind lists its effect as a fraction of the cap per unit of strength (``mental: -1.0`` means a
full-strength modifier takes the whole mental penalty cap). Several modifiers on the same
multiplier stack with diminishing returns (``1 - prod(1 - e)``), so the cap is only approached.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from footystreams.domain.mood import (
    DecayKind,
    ModifierVisibility,
    ResolvedMood,
    StateKind,
    StateModifier,
)
from footystreams.domain.person import Personality
from footystreams.league.mood_config import KindEffect, MoodConfig

TRAIT_MIDPOINT = 50.0
TRAIT_SPAN = 50.0


def decay_factor(modifier: StateModifier, effect: KindEffect, today: dt.date) -> float:
    """1.0 on the start day, fading to 0.0 at expiry; 0.0 before the start or after the end."""
    elapsed = (today - modifier.start_on).days
    if elapsed < 0:
        return 0.0
    if modifier.expires_on is not None and today >= modifier.expires_on:
        return 0.0
    if modifier.decay is DecayKind.HALF_LIFE:
        half_life = modifier.half_life_days or effect.half_life_days or effect.default_days
        return float(0.5 ** (elapsed / half_life))
    end = modifier.expires_on or modifier.start_on + dt.timedelta(days=effect.default_days)
    span = (end - modifier.start_on).days
    return max(0.0, 1.0 - elapsed / span) if span > 0 else 0.0


def _trait(personality: Personality, name: str) -> float:
    return float(getattr(personality, name) - TRAIT_MIDPOINT) / TRAIT_SPAN


def sensitivity(
    kind: StateKind, effect: KindEffect, personality: Personality, config: MoodConfig
) -> float:
    """How strongly this personality feels a modifier of ``kind``; bounded by the config."""
    weights = config.sensitivity.negative if effect.mental < 0 else config.sensitivity.positive
    total = {**weights}
    for trait, weight in config.kind_sensitivity.get(kind.value, {}).items():
        total[trait] = total.get(trait, 0.0) + weight
    value = 1.0 + sum(
        weight * _trait(personality, trait) for trait, weight in sorted(total.items())
    )
    return max(config.sensitivity_floor, min(config.sensitivity_ceiling, value))


def _stack(fractions: Iterable[float]) -> float:
    """Diminishing combination of fractions in [0, 1]: ``1 - prod(1 - f)``."""
    remaining = 1.0
    for fraction in fractions:
        remaining *= 1.0 - min(1.0, max(0.0, fraction))
    return 1.0 - remaining


def _multiplier(contributions: Iterable[float], penalty_cap: float, bonus_cap: float) -> float:
    """``1 + bonus_part - penalty_part`` with both parts stacked and the sum clamped to the caps."""
    values = list(contributions)
    penalty = _stack(-v for v in values if v < 0) * penalty_cap
    bonus = _stack(v for v in values if v > 0) * bonus_cap
    return 1.0 + max(-penalty_cap, min(bonus_cap, bonus - penalty))


def resolve_mood(
    personality: Personality,
    today: dt.date,
    modifiers: Iterable[StateModifier],
    config: MoodConfig,
) -> ResolvedMood:
    """The mood multipliers a player carries into a match played on ``today``."""
    strengths: list[tuple[StateModifier, KindEffect, float]] = []
    for modifier in sorted(modifiers, key=lambda item: item.id):
        effect = config.kinds[modifier.kind.value]
        strength = (
            modifier.magnitude
            * decay_factor(modifier, effect, today)
            * sensitivity(modifier.kind, effect, personality, config)
        )
        if strength > 0:
            strengths.append((modifier, effect, strength))
    return _combine(strengths, config)


def _combine(
    strengths: list[tuple[StateModifier, KindEffect, float]], config: MoodConfig
) -> ResolvedMood:
    caps = config.caps
    mental = [s * e.mental for _, e, s in strengths]
    technical = [s * e.technical for _, e, s in strengths]
    physical = [s * e.physical for _, e, s in strengths]
    volatility = sum(s * e.volatility_add for _, e, s in strengths)
    return ResolvedMood(
        mental_mult=round(_multiplier(mental, caps.mental_penalty, caps.mental_bonus), 4),
        technical_mult=round(
            _multiplier(technical, caps.technical_penalty, caps.technical_bonus), 4
        ),
        physical_mult=round(_multiplier(physical, caps.physical_penalty, caps.physical_bonus), 4),
        volatility_add=round(min(caps.volatility_add_max, volatility), 4),
        contributing_modifier_ids=tuple(m.id for m, _, _ in strengths),
        public_storyline_keys=_storylines(strengths),
    )


def _storylines(strengths: list[tuple[StateModifier, KindEffect, float]]) -> tuple[str, ...]:
    keys = {m.summary_key for m, _, _ in strengths if m.visibility is ModifierVisibility.PUBLIC}
    return tuple(sorted(keys))


def active_modifiers(modifiers: Iterable[StateModifier], today: dt.date) -> list[StateModifier]:
    """Modifiers that have started and not yet expired on ``today``."""
    return [
        m
        for m in modifiers
        if m.start_on <= today and (m.expires_on is None or today < m.expires_on)
    ]
