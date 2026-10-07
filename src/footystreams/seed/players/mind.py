"""Personality and hidden attributes: latent temperament, ambition and sociability."""

from __future__ import annotations

from footystreams.domain.attributes import HiddenAttrs
from footystreams.domain.person import Personality
from footystreams.domain.rng import WorldRng

PERCENT = 100.0
FACTOR_MEAN = 50.0
FACTOR_DEVIATION = 16.0
NOISE_DEVIATION = 9.0
VETERAN_AGE = 30
VETERAN_PROFESSIONALISM_BONUS = 8
YOUTH_PROFESSIONALISM_PENALTY = 8
HIGH = 70
LOW = 30
MIDDLE = 45
EXTREME_CHANCE = 0.03


def _disposition(value: float) -> int:
    return max(0, min(100, round(value)))


def generate_personality(rng: WorldRng, age: int, *, youth: bool) -> Personality:
    """Ten dispositions derived from three latent factors plus noise, and rule-based labels."""
    temperament = rng.normal(FACTOR_MEAN, FACTOR_DEVIATION)
    ambition_factor = rng.normal(FACTOR_MEAN, FACTOR_DEVIATION)
    social = rng.normal(FACTOR_MEAN, FACTOR_DEVIATION)

    def draw(base: float) -> int:
        return _disposition(base + rng.normal(0.0, NOISE_DEVIATION))

    professionalism = draw(
        FACTOR_MEAN + 0.4 * (FACTOR_MEAN - temperament) + 0.3 * (ambition_factor - FACTOR_MEAN)
    )
    if age >= VETERAN_AGE:
        professionalism += VETERAN_PROFESSIONALISM_BONUS
    if youth:
        professionalism -= YOUTH_PROFESSIONALISM_PENALTY
    fields = {
        "ambition": draw(ambition_factor),
        "loyalty": draw(FACTOR_MEAN + 0.5 * (FACTOR_MEAN - ambition_factor)),
        "professionalism": _disposition(professionalism),
        "volatility": draw(temperament),
        "sportsmanship": draw(FACTOR_MEAN + 0.4 * (FACTOR_MEAN - temperament)),
        "ego": draw(
            FACTOR_MEAN + 0.5 * (ambition_factor - FACTOR_MEAN) + 0.3 * (temperament - FACTOR_MEAN)
        ),
        "sociability": draw(social),
        "humor": draw(FACTOR_MEAN + 0.4 * (social - FACTOR_MEAN)),
        "media_openness": draw(FACTOR_MEAN + 0.5 * (social - FACTOR_MEAN)),
        "resilience": draw(
            FACTOR_MEAN + 0.4 * (FACTOR_MEAN - temperament) + 0.2 * (ambition_factor - FACTOR_MEAN)
        ),
    }
    return Personality(
        **fields, archetype_tags=_tags(fields), interview_style=_interview_style(fields)
    )


def _tags(fields: dict[str, int]) -> tuple[str, ...]:
    tags: list[str] = []
    if fields["volatility"] >= HIGH:
        tags.append("hothead")
    if fields["loyalty"] >= HIGH and fields["ambition"] <= MIDDLE:
        tags.append("one_club_man")
    if fields["ambition"] >= HIGH and fields["loyalty"] <= LOW:
        tags.append("mercenary")
    if fields["humor"] >= HIGH:
        tags.append("joker")
    if fields["professionalism"] >= HIGH and fields["sociability"] <= MIDDLE:
        tags.append("quiet_leader")
    return tuple(tags)


# First matching rule wins: (style, ((disposition, "min" | "max", threshold), ...)).
_INTERVIEW_RULES: tuple[tuple[str, tuple[tuple[str, str, int], ...]], ...] = (
    ("cocky", (("ego", "min", HIGH), ("sportsmanship", "max", MIDDLE))),
    ("combative", (("volatility", "min", HIGH),)),
    ("jokey", (("humor", "min", HIGH),)),
    ("guarded", (("media_openness", "max", LOW),)),
    ("humble", (("professionalism", "min", HIGH), ("ego", "max", MIDDLE))),
    ("candid", (("media_openness", "min", HIGH),)),
    ("philosophical", (("resilience", "min", HIGH),)),
)
DEFAULT_INTERVIEW_STYLE = "bland"


def _holds(fields: dict[str, int], condition: tuple[str, str, int]) -> bool:
    name, bound, threshold = condition
    return fields[name] >= threshold if bound == "min" else fields[name] <= threshold


def _interview_style(fields: dict[str, int]) -> str:
    for style, conditions in _INTERVIEW_RULES:
        if all(_holds(fields, condition) for condition in conditions):
            return style
    return DEFAULT_INTERVIEW_STYLE


def generate_hidden(rng: WorldRng, personality: Personality) -> HiddenAttrs:
    """Hidden attributes from Beta draws, with the occasional deliberately extreme character."""
    consistency = rng.beta(5, 3) * PERCENT
    proneness = rng.beta(2, 4) * PERCENT
    dirtiness = rng.beta(2, 5) * PERCENT + 0.3 * (personality.volatility - FACTOR_MEAN)
    if rng.bernoulli(EXTREME_CHANCE):
        consistency = rng.uniform(15.0, 35.0)  # streaky genius
    if rng.bernoulli(EXTREME_CHANCE):
        proneness = rng.uniform(2.0, 10.0)  # iron man
    if rng.bernoulli(EXTREME_CHANCE):
        dirtiness = rng.uniform(75.0, 95.0)  # dirty enforcer

    def clamp(value: float) -> int:
        return max(1, min(100, round(value)))

    return HiddenAttrs(
        consistency=clamp(consistency),
        injury_proneness=clamp(proneness),
        big_match=clamp(rng.beta(4, 4) * PERCENT),
        dirtiness=clamp(dirtiness),
        versatility=clamp(rng.beta(3, 3) * PERCENT),
        adaptability=clamp(rng.beta(4, 4) * PERCENT),
        recovery_rate=clamp(rng.beta(4, 3) * PERCENT),
        development_rate=clamp(rng.beta(4, 3) * PERCENT),
    )
