"""Generate the pool of ten match officials, with a few deliberately distinctive characters."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.referee import HOME_BIAS_MAX, HOME_BIAS_MIN, Referee
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Gender
from footystreams.seed.people import PersonBrief, make_person
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.mind import generate_personality

REFEREE_COUNT = 10
AGE_RANGE = (32, 58)
GENDER_WEIGHTS = {Gender.MALE: 65.0, Gender.FEMALE: 30.0, Gender.NONBINARY: 5.0}
HOME_SHARE = 0.85
REPUTATION_RANGE = (40, 80)
TEMPERAMENT_RANGE = (30, 80)
# Slider centres and deviations for an ordinary official.
ORDINARY: dict[str, tuple[float, float]] = {
    "strictness": (0.50, 0.15),
    "consistency": (0.65, 0.15),
    "home_bias": (0.10, 0.05),
    "card_tendency": (0.50, 0.15),
    "advantage_tendency": (0.50, 0.20),
    "added_time_generosity": (0.50, 0.20),
    "penalty_propensity": (0.50, 0.15),
    "video_reliance": (0.50, 0.20),
    "fitness": (0.80, 0.10),
}


@dataclass(frozen=True, slots=True)
class Character:
    """A distinctive official: fixed slider values and an optional age band."""

    sliders: dict[str, float]
    age: tuple[int, int] = AGE_RANGE


CHARACTERS: tuple[Character, ...] = (
    Character({"strictness": 0.80, "card_tendency": 0.90, "consistency": 0.55}),  # card-happy
    Character(  # the lenient old hand
        {
            "strictness": 0.20,
            "card_tendency": 0.15,
            "consistency": 0.80,
            "advantage_tendency": 0.80,
        },
        age=(58, 62),
    ),
    Character({"home_bias": 0.40}),  # home-bias outlier
    Character({"home_bias": -0.10}),  # leans away
)


def _slider(rng: WorldRng, name: str, character: Character | None) -> float:
    if character is not None and name in character.sliders:
        return character.sliders[name]
    centre, deviation = ORDINARY[name]
    low, high = (HOME_BIAS_MIN, HOME_BIAS_MAX) if name == "home_bias" else (0.0, 1.0)
    return rng.truncated_normal(centre, deviation, low, high)


def generate_referees(ctx: GenerationContext, rng: WorldRng) -> tuple[Referee, ...]:
    """Ten officials: the four characters first, then ordinary officials around the centres."""
    officials: list[Referee] = []
    for index in range(REFEREE_COUNT):
        stream = rng.fork(f"referee:{index}")
        character = CHARACTERS[index] if index < len(CHARACTERS) else None
        age = stream.fork("age").randint(*(character.age if character else AGE_RANGE))
        person = make_person(
            stream.fork("person"),
            ctx,
            PersonBrief(
                kind="referee",
                age=age,
                gender=stream.fork("gender").choice_weighted(GENDER_WEIGHTS),
                region=stream.fork("region").choice(ctx.geography.regions()),
                personality=generate_personality(stream.fork("mind"), age, youth=False),
                reputation=stream.fork("reputation").randint(*REPUTATION_RANGE),
                home_share=HOME_SHARE,
            ),
        )
        sliders = {name: _slider(stream.fork(name), name, character) for name in ORDINARY}
        officials.append(
            Referee.model_validate(
                {
                    **person.model_dump(),
                    **sliders,
                    "temperament": stream.fork("temperament").randint(*TEMPERAMENT_RANGE),
                }
            )
        )
    return tuple(officials)
