"""Media personalities and provider-agnostic voice profiles."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.person import Person
from footystreams.domain.types import GameDate, Unit

ProviderId = str


class AgeRange(StrEnum):
    """Casting age band."""

    YOUNG = "young"
    MID = "mid"
    MATURE = "mature"
    SENIOR = "senior"


class VoiceRegister(StrEnum):
    """Pitch register."""

    LOW = "low"
    MID = "mid"
    HIGH = "high"


class LexiconEntry(DomainModel):
    """Pronunciation lexicon entry."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "token": "R",
        "respelling": "R",
        "ipa": "R",
    }

    token: str
    respelling: str
    ipa: str | None = None


class VoiceCasting(DomainModel):
    """Stable casting sheet (ours, provider-agnostic)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "gender": "R",
        "age_range": "R",
        "accent": "R",
        "timbre": "R",
        "register": "R",
        "base_pace_wpm": "R",
        "pace_variance": "R",
        "energy_range": "R",
        "delivery_notes": "R",
    }

    gender: str
    age_range: AgeRange
    accent: str
    timbre: tuple[str, ...] = ()
    register: VoiceRegister = VoiceRegister.MID
    base_pace_wpm: int = Field(ge=80, le=220, default=150)
    pace_variance: Unit = 0.1
    energy_range: tuple[Unit, Unit] = (0.2, 0.9)
    delivery_notes: str = ""


class VoiceBinding(DomainModel):
    """Provider-specific voice binding."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "voice_id": "R",
        "model": "R",
        "settings": "R",
        "created_on": "R",
        "sample_uri": "R",
    }

    voice_id: str
    model: str
    settings: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    created_on: GameDate | None = None
    sample_uri: str | None = None


class DeliveryProfile(DomainModel):
    """How emotion maps to provider controls."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "emotion_map": "R",
        "interjections": "R",
        "shout_threshold": "R",
        "whisper_threshold": "R",
    }

    emotion_map: Mapping[str, Mapping[str, str]] = Field(default_factory=dict)
    interjections: tuple[str, ...] = ()
    shout_threshold: Unit = 0.8
    whisper_threshold: Unit = 0.2


class VoiceProfile(DomainModel):
    """Provider-agnostic casting sheet plus bindings (O5 deferred)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "schema_version": "R",
        "casting": "R",
        "bindings": "R",
        "lexicon": "R",
        "delivery": "R",
    }

    schema_version: int = 2
    casting: VoiceCasting
    bindings: Mapping[ProviderId, VoiceBinding] = Field(default_factory=dict)
    lexicon: tuple[LexiconEntry, ...] = ()
    delivery: DeliveryProfile = Field(default_factory=DeliveryProfile)


class MediaRole(StrEnum):
    """Broadcast / media role."""

    LEAD_COMMENTATOR = "lead_commentator"
    CO_COMMENTATOR = "co_commentator"
    PUNDIT = "pundit"
    PRESENTER = "presenter"
    REPORTER = "reporter"


class MediaPersonality(Person):
    """On-air talent with a voice profile."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        **Person.__usage__,
        "role": "R",
        "voice": "R",
        "catchphrases": "R",
        "expertise_tags": "R",
    }

    role: MediaRole
    voice: VoiceProfile
    catchphrases: tuple[str, ...] = ()
    expertise_tags: tuple[str, ...] = ()
