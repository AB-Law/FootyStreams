"""Primitive domain types: ids, semantic scales, pitch coordinates, enums."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, ClassVar, NewType

from pydantic import AfterValidator, Field, StringConstraints

from footystreams.domain.base import DomainModel, UsageTag

# --------------------------------------------------------------------------- ids
ID_PATTERN = re.compile(r"^[a-z]{3}_[0-9a-z]{4,12}$")
ID_PREFIXES: Mapping[str, str] = {
    "player": "plr_",
    "manager": "mgr_",
    "club": "clb_",
    "staff": "stf_",
    "referee": "ref_",
    "media": "med_",
    "competition": "cmp_",
    "season": "ssn_",
    "fixture": "fix_",
    "match": "mch_",
    "memory": "mem_",
    "relationship": "rel_",
    "nation": "nat_",
    "city": "cty_",
    "stadium": "std_",
    "proposal": "prp_",
}


def _require_id(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        msg = f"id {value!r} must match {ID_PATTERN.pattern}"
        raise ValueError(msg)
    return value


Id = Annotated[str, AfterValidator(_require_id)]
PlayerId = NewType("PlayerId", str)
ManagerId = NewType("ManagerId", str)
ClubId = NewType("ClubId", str)
StaffId = NewType("StaffId", str)
RefereeId = NewType("RefereeId", str)
MediaId = NewType("MediaId", str)
CompetitionId = NewType("CompetitionId", str)
SeasonId = NewType("SeasonId", str)
FixtureId = NewType("FixtureId", str)
MatchId = NewType("MatchId", str)
MemoryId = NewType("MemoryId", str)
RelationshipId = NewType("RelationshipId", str)
NationId = NewType("NationId", str)
CityId = NewType("CityId", str)
StadiumId = NewType("StadiumId", str)
ProposalId = NewType("ProposalId", str)
RoleId = NewType("RoleId", str)
TraitId = NewType("TraitId", str)
FormationId = NewType("FormationId", str)

GameDate = dt.date

# --------------------------------------------------------------- semantic scales
Attribute = Annotated[int, Field(ge=1, le=100)]
Competence = Annotated[int, Field(ge=0, le=100)]
Reputation = Annotated[int, Field(ge=0, le=100)]
Disposition = Annotated[int, Field(ge=0, le=100)]
Level = Annotated[int, Field(ge=1, le=100)]
AbilityScore = Annotated[int, Field(ge=1, le=100)]
Money = Annotated[int, Field()]

UNIT_DECIMALS = 4


def _round_unit(value: float) -> float:
    rounded = round(value, UNIT_DECIMALS)
    if not 0.0 <= rounded <= 1.0:
        msg = f"Unit {value} must be in [0.0, 1.0]"
        raise ValueError(msg)
    return rounded


def _round_signed(value: float) -> float:
    rounded = round(value, UNIT_DECIMALS)
    if not -1.0 <= rounded <= 1.0:
        msg = f"Signed {value} must be in [-1.0, 1.0]"
        raise ValueError(msg)
    return rounded


Unit = Annotated[float, AfterValidator(_round_unit)]
Signed = Annotated[float, AfterValidator(_round_signed)]

NonEmptyName = Annotated[str, StringConstraints(min_length=1, max_length=40)]


# ----------------------------------------------------------------------- enums
class EntityKind(StrEnum):
    """Kinds that may appear in an EntityRef."""

    PLAYER = "player"
    MANAGER = "manager"
    STAFF = "staff"
    REFEREE = "referee"
    MEDIA = "media"
    CLUB = "club"
    COMPETITION = "competition"
    SEASON = "season"
    FIXTURE = "fixture"
    MATCH = "match"
    MEMORY = "memory"
    RELATIONSHIP = "relationship"
    NATION = "nation"
    CITY = "city"
    STADIUM = "stadium"
    PROPOSAL = "proposal"


class Position(StrEnum):
    """Pitch positions a player may be competent in."""

    GK = "GK"
    RB = "RB"
    LB = "LB"
    CB = "CB"
    RWB = "RWB"
    LWB = "LWB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    RM = "RM"
    LM = "LM"
    RW = "RW"
    LW = "LW"
    SS = "SS"
    ST = "ST"


class PreferredFoot(StrEnum):
    """Which foot a player prefers."""

    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


class Duty(StrEnum):
    """Role duty within a tactics assignment."""

    DEFEND = "defend"
    SUPPORT = "support"
    ATTACK = "attack"


class Gender(StrEnum):
    """Person gender for voice and prose consistency."""

    MALE = "male"
    FEMALE = "female"
    NONBINARY = "nonbinary"


class Pronouns(StrEnum):
    """Pronoun set for LLM prose."""

    HE_HIM = "he/him"
    SHE_HER = "she/her"
    THEY_THEM = "they/them"


OUTFIELD_POSITIONS: frozenset[Position] = frozenset(p for p in Position if p is not Position.GK)


class Pos(DomainModel):
    """Absolute pitch coordinates; home attacks +x in period 1."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"x": "S", "y": "S"}

    x: Unit
    y: Unit


class EntityRef(DomainModel):
    """Polymorphic pointer used by relationships, memories and proposals."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"kind": "L", "id": "L"}

    kind: EntityKind
    id: Id


class RoleAssignment(DomainModel):
    """A preferred or assigned role-and-duty pair."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"role_id": "S", "duty": "S"}

    role_id: RoleId
    duty: Duty
