"""Repository ports: what the league layer may depend on (never SQLAlchemy).

Seams documented here:

* ``Repository[T]`` - get/save/find over one table. ``save`` takes an optional ``expected_rev``
  (optimistic concurrency); every write bumps the stored ``rev``. ``find`` filters on declared
  columns only (equality), ordered by key unless ``order_by`` names a column.
* ``AppendOnlyRepository[T]`` - ledger entries and match events: rows are added, never changed.
* ``UnitOfWork`` - one transaction: ``with uow: ...; uow.commit()``. Leaving the block without
  committing rolls everything back. One transaction per match and per daily-tick stage.
* ``WorldReader`` - the read-only view the pure league functions receive.

Two implementations satisfy these ports (``memory_impl`` and ``sql``) and pass the same contract
suite. The in-memory one does not enforce foreign keys; ``verify_world`` covers integrity.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self

from pydantic import BaseModel

from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.finance import LedgerEntry
from footystreams.domain.fixture import Fixture
from footystreams.domain.manager import Manager
from footystreams.domain.match import Match
from footystreams.domain.media import MediaPersonality
from footystreams.domain.memory import MemoryRecord
from footystreams.domain.mood import StateModifier, WorldEvent
from footystreams.domain.player import Player
from footystreams.domain.proposals import Proposal
from footystreams.domain.referee import Referee
from footystreams.domain.relationship import Relationship
from footystreams.domain.staff import StaffMember
from footystreams.domain.transfer import (
    ContractOffer,
    ScoutReport,
    Transfer,
    TransferBid,
    TransferListing,
    TransferWindow,
)
from footystreams.domain.world import City, Nation, SquadEntry
from footystreams.persistence.records import (
    MetaEntry,
    StageLogEntry,
    StandingsSnapshot,
    StoredEvent,
    SummaryRecord,
)
from footystreams.persistence.specs import ColumnValue

Criteria = Mapping[str, ColumnValue]

# The records are re-exported here so the league layer, which may import only this module from
# persistence, can name the row types the ports hand out.
__all__ = [
    "AppendOnlyRepository",
    "Criteria",
    "MetaEntry",
    "Repositories",
    "Repository",
    "StageLogEntry",
    "StandingsSnapshot",
    "StoredEvent",
    "SummaryRecord",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "Versioned",
    "WorldReader",
]


@dataclass(frozen=True, slots=True)
class Versioned[Row: BaseModel]:
    """A row together with the revision it was read at."""

    entity: Row
    rev: int


class Repository[Row: BaseModel](Protocol):
    """Read and write rows of one table."""

    def get(self, key: str) -> Row | None:
        """The row with this key, or None."""

    def require(self, key: str) -> Row:
        """The row with this key; raises NotFoundError when missing."""

    def get_versioned(self, key: str) -> Versioned[Row] | None:
        """The row and its revision, or None."""

    def save(self, entity: Row, *, expected_rev: int | None = None) -> int:
        """Insert or update and return the new revision (wrong ``expected_rev``: ConflictError)."""

    def save_many(self, entities: Sequence[Row]) -> None:
        """Insert or update several rows (no revision checks)."""

    def delete(self, key: str) -> None:
        """Remove a row; raises NotFoundError when missing."""

    def all(self) -> list[Row]:
        """Every row, ordered by key."""

    def find(self, criteria: Criteria | None = None, *, order_by: str | None = None) -> list[Row]:
        """Rows whose declared columns equal the criteria, ordered by key or by ``order_by``."""

    def count(self, criteria: Criteria | None = None) -> int:
        """How many rows match."""

    def total(self, column: str, criteria: Criteria | None = None) -> int:
        """Sum of an integer column over the matching rows (0 when none)."""


class AppendOnlyRepository[Row: BaseModel](Protocol):
    """Rows that are only ever added."""

    def append(self, entity: Row) -> None:
        """Add a row; a duplicate key raises ConflictError."""

    def append_many(self, entities: Sequence[Row]) -> None:
        """Add several rows atomically with the surrounding transaction."""

    def get(self, key: str) -> Row | None:
        """The row with this key, or None."""

    def all(self) -> list[Row]:
        """Every row, ordered by key."""

    def find(self, criteria: Criteria | None = None, *, order_by: str | None = None) -> list[Row]:
        """Rows whose declared columns equal the criteria."""

    def count(self, criteria: Criteria | None = None) -> int:
        """How many rows match."""

    def total(self, column: str, criteria: Criteria | None = None) -> int:
        """Sum of an integer column over the matching rows (0 when none)."""


class Repositories:
    """Every repository of the database, as attributes (declared here, set by implementations)."""

    meta: Repository[MetaEntry]
    nations: Repository[Nation]
    cities: Repository[City]
    competitions: Repository[Competition]
    seasons: Repository[Season]
    clubs: Repository[Club]
    players: Repository[Player]
    squad_entries: Repository[SquadEntry]
    managers: Repository[Manager]
    staff: Repository[StaffMember]
    referees: Repository[Referee]
    media: Repository[MediaPersonality]
    fixtures: Repository[Fixture]
    matches: Repository[Match]
    summaries: Repository[SummaryRecord]
    standings: Repository[StandingsSnapshot]
    relationships: Repository[Relationship]
    memories: Repository[MemoryRecord]
    proposals: Repository[Proposal]
    modifiers: Repository[StateModifier]
    world_events: Repository[WorldEvent]
    stage_log: Repository[StageLogEntry]
    windows: Repository[TransferWindow]
    listings: Repository[TransferListing]
    bids: Repository[TransferBid]
    offers: Repository[ContractOffer]
    transfers: Repository[Transfer]
    scout_reports: Repository[ScoutReport]
    ledger: AppendOnlyRepository[LedgerEntry]
    events: AppendOnlyRepository[StoredEvent]


class UnitOfWork(Repositories, ABC):
    """One transaction over all repositories."""

    @abstractmethod
    def __enter__(self) -> Self:
        """Begin the transaction."""

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back unless ``commit`` was called; never swallows exceptions."""

    @abstractmethod
    def commit(self) -> None:
        """Make everything written in this block permanent."""

    @abstractmethod
    def rollback(self) -> None:
        """Discard everything written in this block."""


class UnitOfWorkFactory(Protocol):
    """Creates units of work; the league layer receives one of these, never an engine."""

    def __call__(self) -> UnitOfWork:
        """A fresh, not-yet-entered unit of work."""


class WorldReader(Protocol):
    """Read-only view of the world for pure league functions."""

    def current_date(self) -> dt.date:
        """The in-world date (from world_meta)."""

    def club(self, club_id: str) -> Club:
        """A club; raises NotFoundError."""

    def clubs(self) -> list[Club]:
        """All clubs ordered by id."""

    def player(self, player_id: str) -> Player:
        """A player; raises NotFoundError."""

    def squad(self, club_id: str) -> list[Player]:
        """Players under contract with the club, ordered by id."""

    def free_agents(self) -> list[Player]:
        """Players without a club, ordered by id."""

    def manager_of(self, club_id: str) -> Manager | None:
        """The club's manager, if any."""

    def staff_of(self, club_id: str) -> list[StaffMember]:
        """The club's staff, ordered by id."""

    def referees(self) -> list[Referee]:
        """All referees ordered by id."""

    def fixtures(self, season_id: str, matchday: int | None = None) -> list[Fixture]:
        """Fixtures of a season (optionally one matchday), ordered by id."""

    def ledger_balance(self, club_id: str) -> int:
        """Sum of the club's ledger entries."""
