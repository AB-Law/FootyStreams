"""Typed static tables loaded from data/static: formations, traits and injury types.

Roles live in ``roles.py`` (``RoleCatalog``). Tables used by only one layer (name cultures,
archetypes, mood, development, transfer) are defined by that layer instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.injury import InjurySeverity
from footystreams.domain.types import FormationId, Position, TraitId, Unit

FORMATION_SLOTS = 11
GOALKEEPER_SLOT = 0


class FormationSlot(DomainModel):
    """One of eleven formation positions in attack-normalised pitch coordinates."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "slot": "S",
        "position": "S",
        "x": "S",
        "y": "S",
    }

    slot: int = Field(ge=0, le=FORMATION_SLOTS - 1)
    position: Position
    # x: 0 = own goal line, 1 = opposition goal line; y: 0 = top touchline, 1 = bottom.
    x: Unit
    y: Unit


class Formation(DomainModel):
    """A named shape: eleven slots, slot 0 is always the goalkeeper."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"id": "S", "label": "R", "slots": "S"}

    id: FormationId
    label: str = Field(min_length=1, max_length=20)
    slots: tuple[FormationSlot, ...]

    @model_validator(mode="after")
    def _eleven_slots_with_keeper_first(self) -> Self:
        if [slot.slot for slot in self.slots] != list(range(FORMATION_SLOTS)):
            msg = f"formation {self.id} needs slots 0..{FORMATION_SLOTS - 1} in order"
            raise ValueError(msg)
        if self.slots[GOALKEEPER_SLOT].position is not Position.GK:
            msg = f"formation {self.id}: slot {GOALKEEPER_SLOT} must be the goalkeeper"
            raise ValueError(msg)
        if sum(slot.position is Position.GK for slot in self.slots) != 1:
            msg = f"formation {self.id}: exactly one goalkeeper slot"
            raise ValueError(msg)
        return self

    def positions(self) -> tuple[Position, ...]:
        """Slot positions in slot order."""
        return tuple(slot.position for slot in self.slots)


class FormationCatalog(DomainModel):
    """All formations by id."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"formations": "S"}

    formations: Mapping[FormationId, Formation] = Field(min_length=1)


class TraitDefinition(DomainModel):
    """A player trait ("preferred move") and whether the sim reads it yet."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S",
        "label": "R",
        "usage": "R",
        "positions": "R",
        "weight": "R",
    }

    id: TraitId
    label: str = Field(min_length=1, max_length=60)
    usage: Literal["S", "R"]
    # Positions the trait is plausible for; empty means any.
    positions: tuple[Position, ...] = ()
    # Relative frequency among eligible players when the generator hands out traits.
    weight: float = Field(gt=0.0, default=1.0)


class TraitCatalog(DomainModel):
    """All traits by id."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"traits": "S"}

    traits: Mapping[TraitId, TraitDefinition] = Field(min_length=1)


class InjuryType(DomainModel):
    """One kind of injury: where, how bad, how long, how common."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S+L",
        "label": "R",
        "body_part": "S+L",
        "severity": "S+L",
        "min_days": "L",
        "max_days": "L",
        "weight": "S+L",
        "recurrence": "L",
    }

    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)
    body_part: str = Field(min_length=1, max_length=40)
    severity: InjurySeverity
    min_days: int = Field(ge=0)
    max_days: int = Field(ge=0)
    # Relative frequency among injuries of the same severity.
    weight: float = Field(gt=0.0)
    # Extra chance (0-1) the same injury returns, scaled by injury_proneness.
    recurrence: Unit = 0.0

    @model_validator(mode="after")
    def _ordered_durations(self) -> Self:
        if self.max_days < self.min_days:
            msg = f"injury {self.id}: max_days must be >= min_days"
            raise ValueError(msg)
        return self


class InjuryCatalog(DomainModel):
    """All injury types by id."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"injuries": "S+L"}

    injuries: Mapping[str, InjuryType] = Field(min_length=1)

    def of_severity(self, severity: InjurySeverity) -> tuple[InjuryType, ...]:
        """Injury types of one severity, sorted by id for deterministic draws."""
        return tuple(
            sorted(
                (item for item in self.injuries.values() if item.severity is severity),
                key=lambda item: item.id,
            )
        )
