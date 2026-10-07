"""Transfer market entities and OUTSIDE_WORLD counterparty."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import (
    AbilityScore,
    ClubId,
    GameDate,
    Id,
    Money,
    PlayerId,
    SeasonId,
    StaffId,
    Unit,
)

OUTSIDE_WORLD = ClubId("clb_outside")


class WindowKind(StrEnum):
    """Transfer window kind."""

    SUMMER = "summer"
    MIDSEASON = "midseason"


class TransferWindow(DomainModel):
    """Dated transfer window for a season."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "season_id": "L",
        "kind": "L",
        "opens_on": "L",
        "closes_on": "L",
    }

    id: Id
    season_id: SeasonId
    kind: WindowKind
    opens_on: GameDate
    closes_on: GameDate


class TransferListing(DomainModel):
    """Player available for transfer."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "window_id": "L",
        "player_id": "L",
        "club_id": "L",
        "asking_price": "L",
        "listed_on": "L",
    }

    id: Id
    window_id: Id
    player_id: PlayerId
    club_id: ClubId
    asking_price: Money = Field(ge=0)
    listed_on: GameDate


class TransferBid(DomainModel):
    """A bid inside a window (may involve OUTSIDE_WORLD)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "window_id": "L",
        "player_id": "L",
        "from_club_id": "L",
        "to_club_id": "L",
        "fee": "L",
        "round": "L",
        "status": "L",
    }

    id: Id
    window_id: Id
    player_id: PlayerId
    from_club_id: ClubId
    to_club_id: ClubId
    fee: Money = Field(ge=0)
    round: int = Field(ge=1, le=3, default=1)
    status: str = "pending"


class ContractOffer(DomainModel):
    """Player terms offered after a club-club agreement."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "bid_id": "L",
        "player_id": "L",
        "club_id": "L",
        "wage_weekly": "L",
        "length_years": "L",
        "status": "L",
        "round": "L",
    }

    id: Id
    bid_id: Id | None = None
    player_id: PlayerId
    club_id: ClubId
    wage_weekly: Money = Field(ge=0)
    length_years: int = Field(ge=1, le=5)
    status: str = "pending"
    round: int = Field(ge=1, le=3, default=1)


class Transfer(DomainModel):
    """Completed transfer record."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "player_id": "L",
        "from_club_id": "L",
        "to_club_id": "L",
        "fee": "L",
        "completed_on": "L",
    }

    id: Id
    player_id: PlayerId
    from_club_id: ClubId
    to_club_id: ClubId
    fee: Money = Field(ge=0)
    completed_on: GameDate


class ScoutReport(DomainModel):
    """Noisy ability/potential perception."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "R",
        "club_id": "R",
        "scout_id": "R",
        "player_id": "R",
        "perceived_ability": "R",
        "perceived_potential": "R",
        "confidence": "R",
        "created_on": "R",
    }

    id: Id
    club_id: ClubId
    scout_id: StaffId
    player_id: PlayerId
    perceived_ability: AbilityScore
    perceived_potential: AbilityScore
    confidence: Unit
    created_on: GameDate
