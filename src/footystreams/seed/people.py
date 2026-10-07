"""The shared identity of every person kind: name, birth, nationality and look."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.person import Birthplace, Person, Personality
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Gender, Id, NationId, Pronouns
from footystreams.seed.names.book import GeneratedName
from footystreams.seed.players.body import appearance
from footystreams.seed.players.context import (
    HOME_NATIONALITY_SHARE,
    HOME_REGION_SHARE,
    GenerationContext,
)

SECOND_NATIONALITY_CHANCE = 0.08
DAYS_PER_YEAR = 365
PRONOUNS = {
    Gender.MALE: Pronouns.HE_HIM,
    Gender.FEMALE: Pronouns.SHE_HER,
    Gender.NONBINARY: Pronouns.THEY_THEM,
}


@dataclass(frozen=True, slots=True)
class PersonBrief:
    """What the person generator is asked for."""

    kind: str
    age: int
    gender: Gender
    region: str
    personality: Personality
    reputation: int
    home_share: float = HOME_NATIONALITY_SHARE
    family_of: GeneratedName | None = None


def date_of_birth(rng: WorldRng, today: dt.date, age: int) -> dt.date:
    """A birth date that makes the person exactly ``age`` years old on ``today``."""
    birthday_today = dt.date(today.year - age, today.month, min(today.day, 28))
    return birthday_today - dt.timedelta(days=rng.u_int(DAYS_PER_YEAR))


def _nationality(
    rng: WorldRng, ctx: GenerationContext, brief: PersonBrief
) -> tuple[NationId, str, str | None]:
    """Nationality, the name culture to use, and the region of birth (home nation only)."""
    geography = ctx.geography
    if rng.bernoulli(brief.home_share):
        own = rng.bernoulli(HOME_REGION_SHARE)
        region = brief.region if own else rng.choice(geography.regions())
        return geography.home.id, region, region
    nation = rng.choice(geography.foreign)
    return nation.id, nation.name_culture, None


def _second_nationality(rng: WorldRng, ctx: GenerationContext, first: NationId) -> NationId | None:
    if not rng.bernoulli(SECOND_NATIONALITY_CHANCE):
        return None
    others = [nation.id for nation in ctx.geography.nations if nation.id != first]
    return rng.choice(others)


def make_person(rng: WorldRng, ctx: GenerationContext, brief: PersonBrief) -> Person:
    """Build the shared Person core; subclasses add their own fields on top."""
    nationality, culture, region = _nationality(rng.fork("nationality"), ctx, brief)
    name = ctx.names.person(rng.fork("name"), culture, brief.gender, family_of=brief.family_of)
    city = ctx.geography.pick_city(rng.fork("city"), nationality, region)
    return Person(
        id=Id(ctx.ids.next(brief.kind)),
        first_name=name.first_name,
        last_name=name.last_name,
        known_as=name.known_as,
        pronunciation=name.pronunciation,
        gender=brief.gender,
        pronouns=PRONOUNS[brief.gender],
        date_of_birth=date_of_birth(rng.fork("dob"), ctx.today, brief.age),
        nationality=nationality,
        second_nationality=_second_nationality(rng.fork("second"), ctx, nationality),
        birthplace=Birthplace(city=city.name, nation=nationality),
        appearance=appearance(rng.fork("look"), ctx.tables.archetypes.appearance),
        personality=brief.personality,
        reputation=brief.reputation,
    )
