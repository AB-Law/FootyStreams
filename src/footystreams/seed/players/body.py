"""Physical build, footedness and appearance of a generated person."""

from __future__ import annotations

from footystreams.domain.person import Appearance
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import PreferredFoot
from footystreams.seed.players.archetypes import AppearanceSpec, PlayerArchetype

HEIGHT_RANGE = (155, 205)
WEIGHT_RANGE = (55, 105)
BMI_RANGE = (18.2, 26.8)  # inside the Player validator's 18-27 band, with rounding headroom
CM_PER_M = 100.0
LEFT_FOOTED_SHARE = 0.24
TWO_FOOTED_SHARE = 0.06
WEAK_FOOT_RANGE = (15, 85)
TWO_FOOTED_WEAK_FOOT_RANGE = (70, 95)


def height_and_weight(rng: WorldRng, archetype: PlayerArchetype) -> tuple[int, int]:
    """Height and weight from the archetype's distributions, with BMI kept plausible."""
    height_mean, height_deviation = archetype.height
    bmi_mean, bmi_deviation = archetype.bmi
    height = round(rng.truncated_normal(height_mean, height_deviation, *HEIGHT_RANGE))
    bmi = rng.truncated_normal(bmi_mean, bmi_deviation, *BMI_RANGE)
    weight = round(bmi * (height / CM_PER_M) ** 2)
    return height, max(WEIGHT_RANGE[0], min(WEIGHT_RANGE[1], weight))


def foot_and_weak_foot(rng: WorldRng) -> tuple[PreferredFoot, int]:
    """Left 24%, both 6%, right otherwise; a two-footed player has a strong weak foot."""
    roll = rng.u()
    if roll < TWO_FOOTED_SHARE:
        return PreferredFoot.BOTH, rng.randint(*TWO_FOOTED_WEAK_FOOT_RANGE)
    foot = (
        PreferredFoot.LEFT if roll < TWO_FOOTED_SHARE + LEFT_FOOTED_SHARE else PreferredFoot.RIGHT
    )
    return foot, rng.randint(*WEAK_FOOT_RANGE)


def appearance(rng: WorldRng, spec: AppearanceSpec) -> Appearance:
    """Draw an appearance from the weighted tables."""
    return Appearance(
        skin_tone=rng.choice_weighted(spec.skin_tone),
        hair_style=rng.choice_weighted(spec.hair_style),
        hair_colour=rng.choice_weighted(spec.hair_colour),
        facial_hair=rng.choice_weighted(spec.facial_hair),
        build=rng.choice_weighted(spec.build),
    )
