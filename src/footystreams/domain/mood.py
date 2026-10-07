"""Mood resolution, state modifiers and world events."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import EntityRef, GameDate, Id, Unit

# O3 defaults — mood.yaml (M2/M9) will own the live tunables.
DEFAULT_MENTAL_PENALTY_CAP = 0.20
DEFAULT_TECHNICAL_PENALTY_CAP = 0.10
DEFAULT_PHYSICAL_PENALTY_CAP = 0.05
DEFAULT_MENTAL_BONUS_CAP = 0.06
DEFAULT_TECHNICAL_BONUS_CAP = 0.03
DEFAULT_PHYSICAL_BONUS_CAP = 0.01


class ResolvedMood(DomainModel):
    """Frozen mood multipliers copied into a PlayerSnapshot before kickoff."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "mental_mult": "S",
        "technical_mult": "S",
        "physical_mult": "S",
        "volatility_add": "S",
        "contributing_modifier_ids": "S",
        "public_storyline_keys": "S",
    }

    mental_mult: float = Field(default=1.0)
    technical_mult: float = Field(default=1.0)
    physical_mult: float = Field(default=1.0)
    volatility_add: Unit = 0.0
    contributing_modifier_ids: tuple[Id, ...] = ()
    public_storyline_keys: tuple[str, ...] = ()


class StateKind(StrEnum):
    """Discrete mood/life episode kinds (v1)."""

    PERSONAL_TURMOIL = "personal_turmoil"
    FAMILY_MATTER = "family_matter"
    MEDIA_STORM = "media_storm"
    DRESSING_ROOM_ROW = "dressing_room_row"
    MANAGER_ROW = "manager_row"
    CONTRACT_DISPUTE = "contract_dispute"
    TRANSFER_UNREST = "transfer_unrest"
    TRANSFER_SNUB = "transfer_snub"
    HOMESICKNESS = "homesickness"
    FAN_ABUSE = "fan_abuse"
    BLAMED_FOR_DEFEAT = "blamed_for_defeat"
    DROPPED_UNFAIRLY = "dropped_unfairly"
    INJURY_RETURN_JOY = "injury_return_joy"
    NEW_CONTRACT_GLOW = "new_contract_glow"
    AWARD_GLOW = "award_glow"
    DERBY_HERO = "derby_hero"
    TROPHY_GLOW = "trophy_glow"
    MANAGER_BACKING = "manager_backing"
    NEW_SIGNING_ENTHUSIASM = "new_signing_enthusiasm"
    CAPTAINCY_PRIDE = "captaincy_pride"
    RESTED_AND_HAPPY = "rested_and_happy"
    CONFIDENCE_SURGE = "confidence_surge"


class ModifierVisibility(StrEnum):
    """Whether commentary may mention the modifier."""

    PUBLIC = "public"
    PRIVATE = "private"


class DecayKind(StrEnum):
    """How a modifier fades."""

    LINEAR = "linear"
    HALF_LIFE = "half_life"


class ModifierSource(DomainModel):
    """Provenance of a StateModifier."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "origin": "L",
        "world_event_id": "L",
        "proposal_id": "L",
        "match_id": "L",
        "event_ids": "L",
    }

    origin: str
    world_event_id: Id | None = None
    proposal_id: Id | None = None
    match_id: Id | None = None
    event_ids: tuple[Id, ...] = ()


class StateModifier(DomainModel):
    """Time-limited mood episode resolved into ResolvedMood."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "owner": "L",
        "kind": "L",
        "magnitude": "L",
        "start_on": "L",
        "expires_on": "L",
        "decay": "L",
        "half_life_days": "L",
        "source": "L",
        "visibility": "L",
        "summary_key": "L",
        "rev": "L",
    }

    id: Id
    owner: EntityRef
    kind: StateKind
    magnitude: Unit
    start_on: GameDate
    expires_on: GameDate | None = None
    decay: DecayKind = DecayKind.LINEAR
    half_life_days: int | None = None
    source: ModifierSource
    visibility: ModifierVisibility = ModifierVisibility.PRIVATE
    summary_key: str = Field(min_length=1, max_length=80)
    rev: int = 0


class WorldEvent(DomainModel):
    """Shared news-feed fact cited by modifiers and commentary."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "date": "L",
        "kind": "L",
        "participants": "L",
        "facts": "L",
        "visibility": "L",
        "origin": "L",
    }

    id: Id
    date: GameDate
    kind: str = Field(min_length=1, max_length=40)
    participants: tuple[EntityRef, ...] = ()
    facts: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    visibility: ModifierVisibility = ModifierVisibility.PUBLIC
    origin: str = "rule"
