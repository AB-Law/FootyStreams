"""Builders for Person and nested person value objects."""

from __future__ import annotations

import datetime as dt
from typing import Any

from footystreams.domain.person import (
    Appearance,
    Birthplace,
    Person,
    Personality,
    Pronunciation,
)
from footystreams.domain.types import Gender, NationId, Pronouns


def make_personality(**overrides: Any) -> Personality:
    """Build a valid Personality with optional field overrides."""
    values: dict[str, Any] = {
        "ambition": 50,
        "loyalty": 50,
        "professionalism": 50,
        "volatility": 50,
        "sportsmanship": 50,
        "ego": 50,
        "sociability": 50,
        "humor": 50,
        "media_openness": 50,
        "resilience": 50,
        "archetype_tags": (),
        "interview_style": "candid",
    }
    values.update(overrides)
    return Personality(**values)


def make_appearance(**overrides: Any) -> Appearance:
    """Build a valid Appearance with optional field overrides."""
    values: dict[str, Any] = {
        "skin_tone": 4,
        "hair_style": "short",
        "hair_colour": "brown",
        "facial_hair": "none",
        "build": "athletic",
    }
    values.update(overrides)
    return Appearance(**values)


def make_person(**overrides: Any) -> Person:
    """Build a valid Person; Person subclasses may wrap this later."""
    nation = NationId("nat_kesh01")
    values: dict[str, Any] = {
        "id": "plr_test0001",
        "first_name": "Tom",
        "last_name": "Brae",
        "known_as": "Brae",
        "pronunciation": Pronunciation(respelling="BRAY", ipa=None, stress_syllable=0),
        "gender": Gender.MALE,
        "pronouns": Pronouns.HE_HIM,
        "date_of_birth": dt.date(1998, 3, 12),
        "nationality": nation,
        "second_nationality": None,
        "birthplace": Birthplace(city="Kesh", nation=nation),
        "appearance": make_appearance(),
        "personality": make_personality(),
        "reputation": 55,
    }
    values.update(overrides)
    return Person(**values)
