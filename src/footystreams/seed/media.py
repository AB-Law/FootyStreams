"""Generate the broadcast crew from authored personas (``data/static/media_archetypes.yaml``)."""

from __future__ import annotations

from math import sqrt

from footystreams.domain.media import (
    DeliveryProfile,
    LexiconEntry,
    MediaPersonality,
    VoiceBinding,
    VoiceCasting,
    VoiceProfile,
)
from footystreams.domain.person import Personality
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Gender
from footystreams.seed.media_tables import DISPOSITION_FIELDS, CrewMember
from footystreams.seed.people import PersonBrief, make_person
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.mind import generate_personality
from footystreams.seed.static.files import StaticDataError

PLACEHOLDER_PROVIDER = "placeholder"
PLACEHOLDER_MODEL = "placeholder-v0"
PERSONALITY_NOISE = 6
MAX_DISTINCTNESS_ATTEMPTS = 40
REPUTATION_RANGE = (40, 85)


def disposition_distance(left: Personality, right: Personality) -> float:
    """Euclidean distance between two personalities' ten dispositions."""
    return sqrt(sum((getattr(left, f) - getattr(right, f)) ** 2 for f in DISPOSITION_FIELDS))


def _personality(
    rng: WorldRng, member: CrewMember, taken: list[Personality], minimum: float
) -> Personality:
    """Draw around the persona's centres; re-roll until it is distinct from the rest of the crew."""
    for _ in range(MAX_DISTINCTNESS_ATTEMPTS):
        values = {
            field: max(0, min(100, round(rng.normal(centre, PERSONALITY_NOISE))))
            for field, centre in sorted(member.personality.items())
        }
        base = generate_personality(rng.fork("labels"), 40, youth=False)
        candidate = base.model_copy(update=values)
        if all(disposition_distance(candidate, other) >= minimum for other in taken):
            return candidate
    msg = "could not draw a distinct media personality"
    raise StaticDataError(msg)


def _voice(
    member: CrewMember, gender: Gender, slot: int, known_as: str, respelling: str
) -> VoiceProfile:
    spec = member.voice
    return VoiceProfile(
        casting=VoiceCasting(
            gender=gender.value,
            age_range=spec.age_range,
            accent=spec.accent,
            timbre=spec.timbre,
            voice_register=spec.voice_register,
            base_pace_wpm=spec.base_pace_wpm,
            pace_variance=spec.pace_variance,
            energy_range=spec.energy_range,
            delivery_notes=spec.delivery_notes,
        ),
        bindings={
            PLACEHOLDER_PROVIDER: VoiceBinding(
                voice_id=f"voice_placeholder_{slot:02d}", model=PLACEHOLDER_MODEL
            )
        },
        lexicon=(LexiconEntry(token=known_as, respelling=respelling),),
        delivery=DeliveryProfile(interjections=member.interjections),
    )


def generate_crew(ctx: GenerationContext, rng: WorldRng) -> tuple[MediaPersonality, ...]:
    """One person per authored persona, in a stable order, each distinct from the others."""
    tables = ctx.tables.media
    crew: list[MediaPersonality] = []
    taken: list[Personality] = []
    for slot, (key, member) in enumerate(sorted(tables.crew.items()), start=1):
        stream = rng.fork(key)
        gender = stream.fork("gender").choice_weighted(member.gender)
        personality = _personality(stream.fork("mind"), member, taken, tables.distinctness_minimum)
        taken.append(personality)
        age = stream.fork("age").randint(*member.age)
        person = make_person(
            stream.fork("person"),
            ctx,
            PersonBrief(
                kind="media",
                age=age,
                gender=gender,
                region=ctx.geography.regions()[0],
                personality=personality,
                reputation=stream.fork("reputation").randint(*REPUTATION_RANGE),
            ),
        )
        crew.append(
            MediaPersonality(
                **person.model_dump(),
                role=member.role,
                voice=_voice(
                    member, gender, slot, person.known_as, person.pronunciation.respelling
                ),
                catchphrases=member.catchphrases,
                expertise_tags=member.expertise,
            )
        )
    return tuple(crew)
