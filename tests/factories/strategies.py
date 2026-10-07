"""Hypothesis strategies that build valid domain graphs."""

from __future__ import annotations

import datetime as dt

from hypothesis import strategies as st

from footystreams.domain.person import (
    Appearance,
    Birthplace,
    Person,
    Personality,
    Pronunciation,
)
from footystreams.domain.types import Gender, NationId, Pronouns

DISPOSITION = st.integers(min_value=0, max_value=100)
REPUTATION = st.integers(min_value=0, max_value=100)
GAME_DATES = st.dates(min_value=dt.date(1970, 1, 1), max_value=dt.date(2010, 12, 31))
ID_SUFFIX = st.from_regex(r"[0-9a-z]{4,12}", fullmatch=True)
NAMES = st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("L", "N")))
INTERVIEW_STYLES = (
    "guarded",
    "candid",
    "bland",
    "combative",
    "humble",
    "cocky",
    "philosophical",
    "jokey",
)


@st.composite
def pronunciations(draw: st.DrawFn) -> Pronunciation:
    return Pronunciation(
        respelling=draw(NAMES),
        ipa=draw(st.none() | NAMES),
        stress_syllable=draw(st.integers(min_value=0, max_value=5)),
    )


@st.composite
def appearances(draw: st.DrawFn) -> Appearance:
    return Appearance(
        skin_tone=draw(st.integers(min_value=1, max_value=8)),
        hair_style=draw(NAMES),
        hair_colour=draw(NAMES),
        facial_hair=draw(NAMES),
        build=draw(NAMES),
    )


@st.composite
def personalities(draw: st.DrawFn) -> Personality:
    return Personality(
        ambition=draw(DISPOSITION),
        loyalty=draw(DISPOSITION),
        professionalism=draw(DISPOSITION),
        volatility=draw(DISPOSITION),
        sportsmanship=draw(DISPOSITION),
        ego=draw(DISPOSITION),
        sociability=draw(DISPOSITION),
        humor=draw(DISPOSITION),
        media_openness=draw(DISPOSITION),
        resilience=draw(DISPOSITION),
        archetype_tags=tuple(draw(st.lists(NAMES, max_size=3))),
        interview_style=draw(st.sampled_from(INTERVIEW_STYLES)),
    )


@st.composite
def persons(draw: st.DrawFn, *, prefix: str = "plr") -> Person:
    suffix = draw(ID_SUFFIX)
    nation = NationId(f"nat_{draw(ID_SUFFIX)}")
    return Person(
        id=f"{prefix}_{suffix}",
        first_name=draw(NAMES),
        last_name=draw(NAMES),
        known_as=draw(NAMES),
        pronunciation=draw(pronunciations()),
        gender=draw(st.sampled_from(list(Gender))),
        pronouns=draw(st.sampled_from(list(Pronouns))),
        date_of_birth=draw(GAME_DATES),
        nationality=nation,
        second_nationality=None,
        birthplace=Birthplace(city=draw(NAMES), nation=nation),
        appearance=draw(appearances()),
        personality=draw(personalities()),
        reputation=draw(REPUTATION),
    )
