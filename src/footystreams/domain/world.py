"""World records: nations, cities, squad registration, the manifest and the World bundle.

``World`` is a plain frozen dataclass (an in-memory bundle, not a JSON contract of its own): each
collection is written as its own canonical JSON file (seed/world_io) and stored in its own table
(persistence). The record models here are the pieces that have no home in the entity modules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.contract import SquadRole
from footystreams.domain.finance import LedgerEntry
from footystreams.domain.manager import Manager
from footystreams.domain.media import MediaPersonality
from footystreams.domain.memory import MemoryRecord
from footystreams.domain.player import Player, SquadStatus
from footystreams.domain.referee import Referee
from footystreams.domain.relationship import Relationship
from footystreams.domain.staff import StaffMember
from footystreams.domain.types import (
    CityId,
    ClubId,
    GameDate,
    NationId,
    PlayerId,
)

# Clubs outside the league (a player's or manager's earlier employers) have ids with this prefix.
WIDER_WORLD_PREFIX = "clb_wd"


class Nation(DomainModel):
    """A fictional nation; the home nation also owns the regional name cultures."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "name": "R",
        "demonym": "R",
        "is_home": "L",
        "name_culture": "R",
    }

    id: NationId
    name: str = Field(min_length=1, max_length=40)
    demonym: str = Field(min_length=1, max_length=40)
    is_home: bool = False
    # Key into data/static/name_cultures.yaml; regional cultures of the home nation are keyed
    # per city region instead, so this is the nation-wide default.
    name_culture: str = Field(min_length=1, max_length=40)


class City(DomainModel):
    """A place: club home town or player birthplace."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "name": "L",
        "nation_id": "L",
        "region": "R",
        "population": "L",
        "climate": "L",
    }

    id: CityId
    name: str = Field(min_length=1, max_length=40)
    nation_id: NationId
    region: str = Field(default="", max_length=40)
    population: int = Field(ge=0)
    # Key into the climate bands (data/static/climate.yaml); drives weather generation.
    climate: str = Field(min_length=1, max_length=40)


class SquadEntry(DomainModel):
    """The practical link between a club and a player: shirt number and squad status."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club_id": "L",
        "player_id": "L",
        "squad_number": "L",
        "status": "L",
        "squad_role": "L",
    }

    club_id: ClubId
    player_id: PlayerId
    squad_number: int = Field(ge=1, le=99)
    status: SquadStatus
    squad_role: SquadRole


class WorldManifest(DomainModel):
    """What a generated world is and how to recognise it byte for byte."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "world_seed": "L",
        "generator_version": "L",
        "schema_version": "L",
        "counts": "L",
        "content_sha256": "L",
        "created_in_world": "L",
    }

    world_seed: int
    generator_version: str = Field(min_length=1, max_length=20)
    schema_version: str = Field(min_length=1, max_length=20)
    counts: Mapping[str, int]
    content_sha256: str = Field(min_length=64, max_length=64)
    created_in_world: GameDate


@dataclass(frozen=True, slots=True)
class World:
    """Everything a generated world contains, in canonical (id-sorted) order."""

    world_seed: int
    created_in_world: GameDate
    nations: tuple[Nation, ...]
    cities: tuple[City, ...]
    competitions: tuple[Competition, ...]
    seasons: tuple[Season, ...]
    clubs: tuple[Club, ...]
    squad_entries: tuple[SquadEntry, ...]
    players: tuple[Player, ...]
    managers: tuple[Manager, ...]
    staff: tuple[StaffMember, ...]
    referees: tuple[Referee, ...]
    media: tuple[MediaPersonality, ...]
    relationships: tuple[Relationship, ...]
    memories: tuple[MemoryRecord, ...]
    ledger_opening: tuple[LedgerEntry, ...]
