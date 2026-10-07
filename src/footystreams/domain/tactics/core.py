"""TeamTactics core: formation, slots, mentality and module map."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.tactics.modules.v1 import (
    TACTICS_SCHEMA_VERSION,
    ModuleKey,
    TacticModule,
)
from footystreams.domain.types import Duty, FormationId, RoleId

XI_SLOTS = 11


class Mentality(StrEnum):
    """Match mentality band."""

    ULTRA_DEFENSIVE = "ultra_defensive"
    DEFENSIVE = "defensive"
    CAUTIOUS = "cautious"
    BALANCED = "balanced"
    POSITIVE = "positive"
    ATTACKING = "attacking"
    ALL_OUT = "all_out"


class SlotAssignment(DomainModel):
    """One of eleven tactical slots."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "slot": "S",
        "role": "S",
        "duty": "S",
    }

    slot: int = Field(ge=0, le=10)
    role: RoleId
    duty: Duty


class ShapeRef(DomainModel):
    """Named shape reference for a tactical phase."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"formation": "S", "label": "R"}

    formation: FormationId
    label: str = ""


class PhaseStructures(DomainModel):
    """Optional per-phase shape overrides."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "in_possession": "S",
        "out_of_possession": "S",
        "rest_defence": "S",
    }

    in_possession: ShapeRef | None = None
    out_of_possession: ShapeRef | None = None
    rest_defence: ShapeRef | None = None


class PlayerInstruction(DomainModel):
    """Per-player override of a module field."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "slot": "S",
        "module": "S",
        "params": "S",
    }

    slot: int = Field(ge=0, le=10)
    module: ModuleKey
    params: Mapping[str, str | int | float | bool] = Field(default_factory=dict)


class SituationalPlan(DomainModel):
    """Bounded when/apply tactical plan."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "when": "S",
        "apply": "S",
        "priority": "S",
        "cooldown_s": "S",
    }

    when: str = Field(min_length=1, max_length=120)
    apply: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    priority: int = 0
    cooldown_s: int = Field(ge=0, default=0)


class TeamTactics(DomainModel):
    """Versioned tactics: small core plus extensible module registry."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "schema_version": "S",
        "formation": "S",
        "structures": "S",
        "slots": "S",
        "mentality": "S",
        "modules": "S",
        "player_instructions": "S",
        "situational": "S",
        "extensions": "R",
        "roles_locked": "R",
    }

    schema_version: int = TACTICS_SCHEMA_VERSION
    formation: FormationId
    structures: PhaseStructures = Field(default_factory=PhaseStructures)
    slots: tuple[SlotAssignment, ...]
    mentality: Mentality = Mentality.BALANCED
    modules: Mapping[ModuleKey, TacticModule] = Field(default_factory=dict)
    player_instructions: tuple[PlayerInstruction, ...] = ()
    situational: tuple[SituationalPlan, ...] = ()
    extensions: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    roles_locked: bool = False

    @model_validator(mode="after")
    def _eleven_unique_slots(self) -> Self:
        if len(self.slots) != XI_SLOTS:
            msg = f"slots must contain exactly {XI_SLOTS} assignments"
            raise ValueError(msg)
        indices = [slot.slot for slot in self.slots]
        if sorted(indices) != list(range(XI_SLOTS)):
            msg = "slots must cover 0..10 exactly once"
            raise ValueError(msg)
        return self
