"""Club finances and ledger entries."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import ClubId, EntityRef, GameDate, Id, Money, Unit


class LedgerCategory(StrEnum):
    """Income and expense categories on the ledger."""

    MATCHDAY = "matchday"
    MERCHANDISE = "merchandise"
    SPONSORSHIP = "sponsorship"
    BROADCAST = "broadcast"
    PRIZE_MONEY = "prize_money"
    PLAYER_SALES = "player_sales"
    WAGES_PLAYERS = "wages_players"
    WAGES_STAFF = "wages_staff"
    FACILITIES_UPKEEP = "facilities_upkeep"
    YOUTH_ACADEMY = "youth_academy"
    TRANSFER_FEES = "transfer_fees"
    DEBT_SERVICE = "debt_service"
    STADIUM_WORKS = "stadium_works"
    OTHER = "other"


class SponsorDeal(DomainModel):
    """Named sponsorship instalment contract."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "name": "L",
        "annual_value": "L",
        "ends_on": "L",
    }

    name: str = Field(min_length=1, max_length=80)
    annual_value: Money = Field(ge=0)
    ends_on: GameDate


class LedgerEntry(DomainModel):
    """Append-only money movement for a club."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "club_id": "L",
        "date": "L",
        "category": "L",
        "amount": "L",
        "counterparty": "L",
        "ref": "L",
        "memo_key": "L",
    }

    id: Id
    club_id: ClubId
    date: GameDate
    category: LedgerCategory
    amount: Money
    counterparty: EntityRef | None = None
    ref: Mapping[str, str] = Field(default_factory=dict)
    memo_key: str = ""


class ClubFinances(DomainModel):
    """Cached finance state (balance must match ledger sum in verify/)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "balance": "L",
        "wage_budget_weekly": "L",
        "transfer_budget": "L",
        "debt": "L",
        "debt_interest_rate": "L",
        "credit_limit": "L",
        "sponsor_deals": "L",
        "broadcast_share": "L",
        "last_reconciled_on": "L",
    }

    balance: Money
    wage_budget_weekly: Money = Field(ge=0)
    transfer_budget: Money = Field(ge=0)
    debt: Money = Field(ge=0, default=0)
    debt_interest_rate: Unit = 0.0
    credit_limit: Money = Field(ge=0, default=0)
    sponsor_deals: tuple[SponsorDeal, ...] = ()
    broadcast_share: Money = Field(ge=0, default=0)
    last_reconciled_on: GameDate | None = None
