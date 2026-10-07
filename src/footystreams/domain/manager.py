"""Manager person kind and supporting value objects."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.person import Person
from footystreams.domain.types import (
    Attribute,
    ClubId,
    Competence,
    FormationId,
    GameDate,
    Money,
    Unit,
)

MAX_FALLBACK_FORMATIONS = 3


class ManagerStyle(StrEnum):
    """Coarse named tactical style tag."""

    POSSESSION = "possession"
    COUNTER_ATTACKING = "counter_attacking"
    HIGH_PRESS = "high_press"
    DIRECT = "direct"
    BALANCED = "balanced"
    LOW_BLOCK = "low_block"
    WING_PLAY = "wing_play"
    GEGEN_PRESS = "gegen_press"


class TouchlineBehaviour(StrEnum):
    """Renderer flavour for sideline demeanour."""

    CALM = "calm"
    ANIMATED = "animated"
    FURIOUS = "furious"
    STOIC = "stoic"
    THEATRICAL = "theatrical"


class PressTone(StrEnum):
    """Press-conference tone."""

    CALM = "calm"
    FIERY = "fiery"
    DRY = "dry"
    CHARMING = "charming"
    EVASIVE = "evasive"
    BLUNT = "blunt"


class Philosophy(DomainModel):
    """Slider set seeding default tactics and AI baseline."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "possession_preference": "S",
        "directness": "S",
        "pressing_intensity": "S",
        "tempo": "S",
        "width": "S",
        "defensive_line": "S",
        "risk_taking": "S",
        "set_piece_focus": "L",
        "rotation_tendency": "L",
        "youth_trust": "L",
    }

    possession_preference: Unit
    directness: Unit
    pressing_intensity: Unit
    tempo: Unit
    width: Unit
    defensive_line: Unit
    risk_taking: Unit
    set_piece_focus: Unit = 0.5
    rotation_tendency: Unit = 0.5
    youth_trust: Unit = 0.5


class SubHabits(DomainModel):
    """Substitution *preferences* for the AI manager (not hard match rules).

    The sim (M4/M9) interprets these alongside match state: injuries, reds,
    scoreline and fatigue can force earlier changes even when
    ``earliest_minute`` is high. ``reacts_to_cards`` / ``fresh_legs_bias``
    weight those overrides; they are not applied in M1 (models only).
    """

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "earliest_minute": "S",
        "preferred_windows": "S",
        "aggressiveness": "S",
        "fresh_legs_bias": "S",
        "protect_lead_bias": "S",
        "chase_game_bias": "S",
        "reacts_to_cards": "S",
        "uses_all_subs": "S",
    }

    # Preferred earliest *planned* tactical sub; emergencies ignore this.
    earliest_minute: int = Field(ge=0, le=90)
    preferred_windows: tuple[int, ...] = ()
    aggressiveness: Unit
    fresh_legs_bias: Unit
    protect_lead_bias: Unit
    chase_game_bias: Unit
    reacts_to_cards: Unit
    uses_all_subs: bool = True


class ManagerAttrs(DomainModel):
    """Manager skill attributes."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "tactical_knowledge": "S",
        "man_management": "S",
        "motivation": "S",
        "youth_development": "L",
        "judging_ability": "L",
        "judging_potential": "L",
        "adaptability": "S",
        "discipline": "S",
        "fitness_coaching": "L",
        "set_piece_coaching": "R",
        "negotiation": "L",
        "media_handling": "R",
    }

    tactical_knowledge: Attribute
    man_management: Attribute
    motivation: Attribute
    youth_development: Attribute
    judging_ability: Attribute
    judging_potential: Attribute
    adaptability: Attribute
    discipline: Attribute
    fitness_coaching: Attribute
    set_piece_coaching: Attribute
    negotiation: Attribute
    media_handling: Attribute


class PressProfile(DomainModel):
    """Press-conference generator input."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "tone": "R",
        "candour": "R",
        "deflection": "R",
        "blame_tendency": "R",
        "bold_claims": "R",
        "mind_games": "R",
        "humor": "R",
    }

    tone: PressTone
    candour: Unit
    deflection: Unit
    blame_tendency: Unit
    bold_claims: Unit
    mind_games: Unit
    humor: Unit


class ObjectiveKind(StrEnum):
    """Board/manager objective kinds."""

    LEAGUE_POSITION = "league_position"
    CUP_ROUND = "cup_round"
    FINANCIAL = "financial"
    YOUTH = "youth"


class Objective(DomainModel):
    """A measurable board or contract objective."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "L",
        "target": "L",
        "deadline": "L",
    }

    kind: ObjectiveKind
    target: str = Field(min_length=1, max_length=80)
    deadline: GameDate | None = None


class ManagerContract(DomainModel):
    """Employment terms for a manager."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club_id": "L",
        "start": "L",
        "end": "L",
        "wage_weekly": "L",
        "release_clause": "L",
        "objectives": "L",
    }

    club_id: ClubId
    start: GameDate
    end: GameDate
    wage_weekly: Money = Field(ge=0)
    release_clause: Money | None = None
    objectives: tuple[Objective, ...] = ()


class ManagerStint(DomainModel):
    """One managerial spell at a club."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club_id": "L",
        "from_date": "L",
        "to_date": "L",
        "played": "R",
        "won": "R",
        "drawn": "R",
        "lost": "R",
        "trophies": "R",
    }

    club_id: ClubId
    from_date: GameDate
    to_date: GameDate | None = None
    played: int = Field(ge=0, default=0)
    won: int = Field(ge=0, default=0)
    drawn: int = Field(ge=0, default=0)
    lost: int = Field(ge=0, default=0)
    trophies: tuple[str, ...] = ()


class Manager(Person):
    """Club manager with philosophy, habits and attributes."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        **Person.__usage__,
        "style": "S",
        "philosophy": "S",
        "preferred_formation": "S",
        "fallback_formations": "S",
        "formation_proficiency": "S",
        "flexibility": "S",
        "substitution_habits": "S",
        "touchline_behaviour": "R",
        "attributes": "S",
        "press_style": "R",
        "contract": "L",
        "career_history": "L",
        "reputation": "L",
    }

    style: ManagerStyle
    philosophy: Philosophy
    preferred_formation: FormationId
    fallback_formations: tuple[FormationId, ...] = ()
    formation_proficiency: Mapping[FormationId, Competence] = Field(default_factory=dict)
    flexibility: Unit
    substitution_habits: SubHabits
    touchline_behaviour: TouchlineBehaviour = TouchlineBehaviour.CALM
    attributes: ManagerAttrs
    press_style: PressProfile
    contract: ManagerContract | None = None
    career_history: tuple[ManagerStint, ...] = ()
    # reputation inherited from Person; usage retagged above for manager context
