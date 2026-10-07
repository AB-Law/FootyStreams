"""Builders for Player and attribute groups."""

from __future__ import annotations

from typing import Any

from footystreams.domain.attributes import (
    GoalkeepingAttrs,
    HiddenAttrs,
    MentalAttrs,
    PhysicalAttrs,
    TechnicalAttrs,
)
from footystreams.domain.person import Person
from footystreams.domain.player import Player, PlayerStatus, SquadStatus
from footystreams.domain.types import Position, PreferredFoot, RoleId
from tests.factories.person import make_person

_PERSON_FIELDS = frozenset(Person.model_fields)


def make_technical(**overrides: Any) -> TechnicalAttrs:
    """Build TechnicalAttrs with a flat default skill level."""
    values = dict.fromkeys(TechnicalAttrs.model_fields, 50)
    values.update(overrides)
    return TechnicalAttrs(**values)


def make_mental(**overrides: Any) -> MentalAttrs:
    """Build MentalAttrs with a flat default skill level."""
    values = dict.fromkeys(MentalAttrs.model_fields, 50)
    values.update(overrides)
    return MentalAttrs(**values)


def make_physical(**overrides: Any) -> PhysicalAttrs:
    """Build PhysicalAttrs with a flat default skill level."""
    values = dict.fromkeys(PhysicalAttrs.model_fields, 50)
    values.update(overrides)
    return PhysicalAttrs(**values)


def make_goalkeeping(**overrides: Any) -> GoalkeepingAttrs:
    """Build GoalkeepingAttrs with low defaults suitable for outfielders."""
    values = dict.fromkeys(GoalkeepingAttrs.model_fields, 15)
    values.update(overrides)
    return GoalkeepingAttrs(**values)


def make_hidden(**overrides: Any) -> HiddenAttrs:
    """Build HiddenAttrs with a flat default skill level."""
    values = dict.fromkeys(HiddenAttrs.model_fields, 50)
    values.update(overrides)
    return HiddenAttrs(**values)


def make_player(**overrides: Any) -> Player:
    """Build a valid outfield Player; override fields as needed for tests."""
    person_overrides = {key: overrides.pop(key) for key in list(overrides) if key in _PERSON_FIELDS}
    base_person = make_person(**person_overrides)
    competence: dict[Position, int] = overrides.pop(
        "position_competence",
        {Position.ST: 90, Position.SS: 70, Position.AM: 55, Position.GK: 10},
    )
    values: dict[str, Any] = {
        **base_person.model_dump(),
        "height_cm": 180,
        "weight_kg": 75,
        "preferred_foot": PreferredFoot.RIGHT,
        "weak_foot": 45,
        "squad_number": 9,
        "position_competence": competence,
        "primary_position": max(competence, key=competence.__getitem__),
        "role_familiarity": {RoleId("poacher"): 80},
        "preferred_roles": (),
        "traits": (),
        "technical": make_technical(),
        "mental": make_mental(),
        "physical": make_physical(),
        "goalkeeping": make_goalkeeping(),
        "hidden": make_hidden(),
        "ability_current": 70,
        "ability_potential": 78,
        "status": PlayerStatus.ACTIVE,
        "squad_status": SquadStatus.FIRST_TEAM,
        "is_youth": False,
    }
    values.update(overrides)
    if "primary_position" not in overrides:
        competence_final = values["position_competence"]
        values["primary_position"] = max(competence_final, key=competence_final.__getitem__)
    return Player(**values)
