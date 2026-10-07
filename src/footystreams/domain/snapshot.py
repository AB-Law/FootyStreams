"""PlayerSnapshot frozen for match input."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.attributes import (
    GoalkeepingAttrs,
    HiddenAttrs,
    MentalAttrs,
    PhysicalAttrs,
    TechnicalAttrs,
)
from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.mood import ResolvedMood
from footystreams.domain.types import (
    Attribute,
    Competence,
    PlayerId,
    Position,
    PreferredFoot,
    Reputation,
    RoleId,
    TraitId,
    Unit,
)


class PlayerSnapshot(DomainModel):
    """Sim-relevant frozen copy of a player for one match."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S",
        "known_as": "S",
        "age": "S",
        "height_cm": "S",
        "weight_kg": "S",
        "preferred_foot": "S",
        "weak_foot": "S",
        "technical": "S",
        "mental": "S",
        "physical": "S",
        "goalkeeping": "S",
        "hidden": "S",
        "position_competence": "S",
        "role_familiarity": "S",
        "traits": "S",
        "form": "S",
        "morale": "S",
        "mood": "S",
        "fitness": "S",
        "fatigue": "S",
        "match_sharpness": "S",
        "volatility": "S",
        "sportsmanship": "S",
        "reputation": "S",
        "squad_number": "S",
        "public_storylines": "S",
    }

    id: PlayerId
    known_as: str = Field(min_length=1, max_length=40)
    age: int = Field(ge=15, le=45)
    height_cm: int
    weight_kg: int
    preferred_foot: PreferredFoot
    weak_foot: Attribute
    technical: TechnicalAttrs
    mental: MentalAttrs
    physical: PhysicalAttrs
    goalkeeping: GoalkeepingAttrs
    hidden: HiddenAttrs
    position_competence: Mapping[Position, Competence]
    role_familiarity: Mapping[RoleId, Competence] = Field(default_factory=dict)
    traits: tuple[TraitId, ...] = ()
    form: Unit
    morale: Unit
    mood: ResolvedMood = Field(default_factory=ResolvedMood)
    fitness: Unit
    fatigue: Unit
    match_sharpness: Unit
    volatility: int = Field(ge=0, le=100)
    sportsmanship: int = Field(ge=0, le=100)
    reputation: Reputation
    squad_number: int | None = None
    public_storylines: tuple[str, ...] = ()
