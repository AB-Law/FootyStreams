"""Player attribute groups: technical, mental, physical, goalkeeping, hidden."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import Attribute


class TechnicalAttrs(DomainModel):
    """Outfield technical skills (13)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "finishing": "S",
        "long_shots": "S",
        "heading": "S",
        "first_touch": "S",
        "dribbling": "S",
        "short_passing": "S",
        "long_passing": "S",
        "crossing": "S",
        "tackling": "S",
        "marking": "S",
        "set_piece_delivery": "S",
        "penalty_taking": "S",
        "ball_shielding": "S",
    }

    finishing: Attribute
    long_shots: Attribute
    heading: Attribute
    first_touch: Attribute
    dribbling: Attribute
    short_passing: Attribute
    long_passing: Attribute
    crossing: Attribute
    tackling: Attribute
    marking: Attribute
    set_piece_delivery: Attribute
    penalty_taking: Attribute
    ball_shielding: Attribute


class MentalAttrs(DomainModel):
    """Mental skills (14)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "vision": "S",
        "decisions": "S",
        "composure": "S",
        "anticipation": "S",
        "positioning": "S",
        "off_ball_movement": "S",
        "work_rate": "S",
        "aggression": "S",
        "bravery": "S",
        "concentration": "S",
        "determination": "S",
        "teamwork": "S",
        "flair": "S",
        "leadership": "S+L",
    }

    vision: Attribute
    decisions: Attribute
    composure: Attribute
    anticipation: Attribute
    positioning: Attribute
    off_ball_movement: Attribute
    work_rate: Attribute
    aggression: Attribute
    bravery: Attribute
    concentration: Attribute
    determination: Attribute
    teamwork: Attribute
    flair: Attribute
    leadership: Attribute


class PhysicalAttrs(DomainModel):
    """Physical skills (8)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "pace": "S",
        "acceleration": "S",
        "stamina": "S",
        "strength": "S",
        "agility": "S",
        "balance": "S",
        "jumping_reach": "S",
        "natural_fitness": "S+L",
    }

    pace: Attribute
    acceleration: Attribute
    stamina: Attribute
    strength: Attribute
    agility: Attribute
    balance: Attribute
    jumping_reach: Attribute
    natural_fitness: Attribute


class GoalkeepingAttrs(DomainModel):
    """Goalkeeping skills (7)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "handling": "S",
        "shot_stopping": "S",
        "aerial_command": "S",
        "distribution": "S",
        "one_on_ones": "S",
        "sweeping": "S",
        "communication": "S",
    }

    handling: Attribute
    shot_stopping: Attribute
    aerial_command: Attribute
    distribution: Attribute
    one_on_ones: Attribute
    sweeping: Attribute
    communication: Attribute


class HiddenAttrs(DomainModel):
    """Hidden attributes never shown directly to commentary."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "consistency": "S",
        "injury_proneness": "S+L",
        "big_match": "S",
        "dirtiness": "S",
        "versatility": "L",
        "adaptability": "L",
        "recovery_rate": "L",
        "development_rate": "L",
    }

    consistency: Attribute
    injury_proneness: Attribute
    big_match: Attribute
    dirtiness: Attribute
    versatility: Attribute
    adaptability: Attribute
    recovery_rate: Attribute
    development_rate: Attribute


def attribute_map(group: DomainModel) -> Mapping[str, int]:
    """Flat name→value map for one attribute group."""
    return {name: int(value) for name, value in group.model_dump().items()}
