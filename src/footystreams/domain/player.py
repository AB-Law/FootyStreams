"""Player entity: person plus physical profile, positions, attributes and condition.

Training and development fields are added in a later M1 slice.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.attributes import (
    GoalkeepingAttrs,
    HiddenAttrs,
    MentalAttrs,
    PhysicalAttrs,
    TechnicalAttrs,
)
from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.contract import Contract
from footystreams.domain.development import DevelopmentEntry, TrainingPlan
from footystreams.domain.injury import Discipline, Injury, InjuryRecord, MoraleFactor, Suspension
from footystreams.domain.person import Person
from footystreams.domain.types import (
    OUTFIELD_POSITIONS,
    AbilityScore,
    Attribute,
    ClubId,
    Competence,
    GameDate,
    Money,
    Position,
    PreferredFoot,
    RoleAssignment,
    RoleId,
    TraitId,
    Unit,
)

MIN_PLAYER_HEIGHT_CM = 155
MAX_PLAYER_HEIGHT_CM = 205
MIN_PLAYER_WEIGHT_KG = 55
MAX_PLAYER_WEIGHT_KG = 105
MIN_BMI = 18.0
MAX_BMI = 27.0
NATURAL_POSITION_FLOOR = 85
GK_OUTFIELD_CAP = 30
MAX_PREFERRED_ROLES = 4
MAX_TRAITS = 6
MAX_FORM_HISTORY = 10
MAX_MORALE_FACTORS = 12
MAX_DEVELOPMENT_LOG = 24
DEFAULT_ROLE_FAMILIARITY = 35


class PlayerStatus(StrEnum):
    """Lifecycle status of a player in the world."""

    ACTIVE = "active"
    RETIRED = "retired"
    FREE_AGENT = "free_agent"


class SquadStatus(StrEnum):
    """Where the player sits in a club structure."""

    FIRST_TEAM = "first_team"
    RESERVE = "reserve"
    YOUTH = "youth"
    LOANED_OUT = "loaned_out"
    FREE_AGENT = "free_agent"


class CareerStint(DomainModel):
    """One club spell in a player's career history."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club_id": "L",
        "from_date": "L",
        "to_date": "L",
        "apps": "L",
        "goals": "L",
    }

    club_id: ClubId
    from_date: GameDate
    to_date: GameDate | None = None
    apps: int = Field(ge=0, default=0)
    goals: int = Field(ge=0, default=0)


class Player(Person):
    """A footballer: attributes, positions, physical profile and condition."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        **Person.__usage__,
        "height_cm": "S",
        "weight_kg": "S",
        "preferred_foot": "S",
        "weak_foot": "S",
        "squad_number": "L",
        "position_competence": "S",
        "primary_position": "L",
        "role_familiarity": "S",
        "preferred_roles": "S",
        "traits": "S",
        "technical": "S",
        "mental": "S",
        "physical": "S",
        "goalkeeping": "S",
        "hidden": "S",
        "ability_current": "L",
        "ability_potential": "L",
        "form": "S+L",
        "form_history": "L",
        "morale": "S+L",
        "morale_factors": "L",
        "fitness": "S+L",
        "fatigue": "S+L",
        "match_sharpness": "S+L",
        "current_injury": "S+L",
        "injury_history": "L",
        "suspension": "L",
        "discipline": "L",
        "contract": "L",
        "market_value": "L",
        "career_history": "L",
        "training": "L",
        "development_log": "L",
        "status": "L",
        "squad_status": "L",
        "is_youth": "L",
    }

    height_cm: int = Field(ge=MIN_PLAYER_HEIGHT_CM, le=MAX_PLAYER_HEIGHT_CM)
    weight_kg: int = Field(ge=MIN_PLAYER_WEIGHT_KG, le=MAX_PLAYER_WEIGHT_KG)
    preferred_foot: PreferredFoot
    weak_foot: Attribute
    squad_number: int | None = Field(default=None, ge=1, le=99)
    position_competence: Mapping[Position, Competence]
    primary_position: Position
    role_familiarity: Mapping[RoleId, Competence] = Field(default_factory=dict)
    preferred_roles: tuple[RoleAssignment, ...] = ()
    traits: tuple[TraitId, ...] = ()
    technical: TechnicalAttrs
    mental: MentalAttrs
    physical: PhysicalAttrs
    goalkeeping: GoalkeepingAttrs
    hidden: HiddenAttrs
    ability_current: AbilityScore
    ability_potential: AbilityScore
    form: Unit = 0.5
    form_history: tuple[float, ...] = ()
    morale: Unit = 0.5
    morale_factors: tuple[MoraleFactor, ...] = ()
    fitness: Unit = 1.0
    fatigue: Unit = 0.0
    match_sharpness: Unit = 0.5
    current_injury: Injury | None = None
    injury_history: tuple[InjuryRecord, ...] = ()
    suspension: Suspension | None = None
    discipline: Discipline = Field(default_factory=Discipline)
    contract: Contract | None = None
    market_value: Money = 0
    career_history: tuple[CareerStint, ...] = ()
    training: TrainingPlan = Field(default_factory=TrainingPlan)
    development_log: tuple[DevelopmentEntry, ...] = ()
    status: PlayerStatus = PlayerStatus.ACTIVE
    squad_status: SquadStatus = SquadStatus.FIRST_TEAM
    is_youth: bool = False

    def role_familiarity_or_default(self, role_id: RoleId) -> Competence:
        """Return familiarity for ``role_id``, defaulting to 35 when absent."""
        return self.role_familiarity.get(role_id, DEFAULT_ROLE_FAMILIARITY)

    @model_validator(mode="after")
    def _check_player_invariants(self) -> Self:
        self._check_bmi()
        self._check_ability()
        self._check_positions()
        self._check_lists()
        return self

    def _check_bmi(self) -> None:
        height_m = self.height_cm / 100.0
        bmi = self.weight_kg / (height_m * height_m)
        if not MIN_BMI <= bmi <= MAX_BMI:
            msg = f"BMI {bmi:.1f} outside [{MIN_BMI}, {MAX_BMI}]"
            raise ValueError(msg)

    def _check_ability(self) -> None:
        if self.ability_potential < self.ability_current:
            msg = "ability_potential must be >= ability_current"
            raise ValueError(msg)

    def _check_positions(self) -> None:
        if not self.position_competence:
            msg = "position_competence must not be empty"
            raise ValueError(msg)
        primary = max(self.position_competence, key=lambda pos: self.position_competence[pos])
        if primary != self.primary_position:
            msg = "primary_position must be argmax of position_competence"
            raise ValueError(msg)
        if self.is_youth:
            return
        if max(self.position_competence.values()) < NATURAL_POSITION_FLOOR:
            msg = f"non-youth needs a position competence >= {NATURAL_POSITION_FLOOR}"
            raise ValueError(msg)
        gk = self.position_competence.get(Position.GK, 0)
        outfield = [self.position_competence.get(pos, 0) for pos in OUTFIELD_POSITIONS]
        if gk >= NATURAL_POSITION_FLOOR and any(value > GK_OUTFIELD_CAP for value in outfield):
            msg = f"GK natural players must keep outfield competence <= {GK_OUTFIELD_CAP}"
            raise ValueError(msg)
        if gk < NATURAL_POSITION_FLOOR and gk > GK_OUTFIELD_CAP:
            msg = f"outfield players must keep GK competence <= {GK_OUTFIELD_CAP}"
            raise ValueError(msg)

    def _check_lists(self) -> None:
        if len(self.preferred_roles) > MAX_PREFERRED_ROLES:
            msg = f"preferred_roles max {MAX_PREFERRED_ROLES}"
            raise ValueError(msg)
        if len(self.traits) > MAX_TRAITS:
            msg = f"traits max {MAX_TRAITS}"
            raise ValueError(msg)
        if len(self.form_history) > MAX_FORM_HISTORY:
            msg = f"form_history keeps at most {MAX_FORM_HISTORY} ratings"
            raise ValueError(msg)
        if len(self.morale_factors) > MAX_MORALE_FACTORS:
            msg = f"morale_factors max {MAX_MORALE_FACTORS}"
            raise ValueError(msg)
        if len(self.development_log) > MAX_DEVELOPMENT_LOG:
            msg = f"development_log keeps at most {MAX_DEVELOPMENT_LOG} entries"
            raise ValueError(msg)
