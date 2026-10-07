"""Person base, personality and appearance shared by all people kinds."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import (
    Disposition,
    GameDate,
    Gender,
    Id,
    NationId,
    NonEmptyName,
    Pronouns,
    Reputation,
)


class Pronunciation(DomainModel):
    """TTS pronunciation hint produced by the name generator."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "respelling": "R",
        "ipa": "R",
        "stress_syllable": "R",
    }

    respelling: NonEmptyName
    ipa: str | None = None
    stress_syllable: int = Field(ge=0)


class Appearance(DomainModel):
    """Pixel-renderer appearance cues."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "skin_tone": "R",
        "hair_style": "R",
        "hair_colour": "R",
        "facial_hair": "R",
        "build": "R",
    }

    skin_tone: int = Field(ge=1, le=8)
    hair_style: NonEmptyName
    hair_colour: NonEmptyName
    facial_hair: str = Field(min_length=1, max_length=40)
    build: NonEmptyName


class Birthplace(DomainModel):
    """City and nation of birth for commentary colour."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"city": "R", "nation": "R"}

    city: NonEmptyName
    nation: NationId


class Personality(DomainModel):
    """Disposition sliders shared by players and managers."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "ambition": "R",
        "loyalty": "R",
        "professionalism": "L",
        "volatility": "S",
        "sportsmanship": "R",
        "ego": "R",
        "sociability": "R",
        "humor": "R",
        "media_openness": "R",
        "resilience": "L",
        "archetype_tags": "R",
        "interview_style": "R",
    }

    ambition: Disposition
    loyalty: Disposition
    professionalism: Disposition
    volatility: Disposition
    sportsmanship: Disposition
    ego: Disposition
    sociability: Disposition
    humor: Disposition
    media_openness: Disposition
    resilience: Disposition
    archetype_tags: tuple[str, ...] = ()
    interview_style: str = Field(min_length=1, max_length=40)


class Person(DomainModel):
    """Shared identity fields for every person kind in the world."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S+L",
        "first_name": "R",
        "last_name": "R",
        "known_as": "L",
        "pronunciation": "R",
        "gender": "R",
        "pronouns": "R",
        "date_of_birth": "S+L",
        "nationality": "R",
        "second_nationality": "R",
        "birthplace": "R",
        "appearance": "R",
        "personality": "R",
        "reputation": "S+L",
    }

    id: Id
    first_name: NonEmptyName
    last_name: NonEmptyName
    known_as: NonEmptyName
    pronunciation: Pronunciation
    gender: Gender
    pronouns: Pronouns
    date_of_birth: GameDate
    nationality: NationId
    second_nationality: NationId | None = None
    birthplace: Birthplace
    appearance: Appearance
    personality: Personality
    reputation: Reputation

    def age_on(self, on: GameDate) -> int:
        """Return whole years of age on the in-world date ``on``."""
        years = on.year - self.date_of_birth.year
        before_birthday = (on.month, on.day) < (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        return years - 1 if before_birthday else years

    @model_validator(mode="after")
    def _names_non_blank(self) -> Person:
        if not self.known_as.strip():
            msg = "known_as must not be blank"
            raise ValueError(msg)
        return self
