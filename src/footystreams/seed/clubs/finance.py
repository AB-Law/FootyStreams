"""Club finances: income, budgets, sponsors, debt and the opening ledger entry."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.finance import ClubFinances, LedgerCategory, LedgerEntry, SponsorDeal
from footystreams.domain.ids import IdMint
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Id, Money
from footystreams.seed.clubs.archetypes import ClubArchetype

MILLION = 1_000_000
WEEKS_PER_YEAR = 52
SPONSOR_DEALS = (2, 3)
SPONSOR_SHARE_OF_INCOME = (0.04, 0.07)
SPONSOR_YEARS = (1, 3)
BROADCAST_SHARE_OF_INCOME = 0.22
CREDIT_LIMIT_SHARE_OF_INCOME = 0.40
INTEREST_RATE_RANGE = (0.03, 0.06)
DISTRESS_DEBT_SHARE = 0.8  # debt above this share of income raises the interest rate
DISTRESS_SURCHARGE = 0.015


def annual_income(rng: WorldRng, archetype: ClubArchetype) -> Money:
    """Yearly income in crowns, drawn from the archetype's range."""
    return rng.randint(*archetype.income_m) * MILLION


def wage_budget_weekly(income: Money, archetype: ClubArchetype, rng: WorldRng) -> Money:
    """Weekly player-wage budget: the archetype's share of income spread over 52 weeks."""
    return round(income * rng.uniform(*archetype.wage_budget_share) / WEEKS_PER_YEAR)


def make_finances(
    rng: WorldRng,
    archetype: ClubArchetype,
    sponsors: tuple[str, ...],
    today: dt.date,
) -> tuple[ClubFinances, Money]:
    """Finance state for a club, plus its annual income (the generator needs it for wages)."""
    income = annual_income(rng.fork("income"), archetype)
    debt = rng.randint(*archetype.debt_m) * MILLION
    rate = rng.uniform(*INTEREST_RATE_RANGE)
    if debt > income * DISTRESS_DEBT_SHARE:
        rate += DISTRESS_SURCHARGE
    chosen = rng.fork("sponsors").shuffled(sponsors)[: rng.randint(*SPONSOR_DEALS)]
    deals = tuple(
        SponsorDeal(
            name=name,
            annual_value=round(income * rng.uniform(*SPONSOR_SHARE_OF_INCOME)),
            ends_on=dt.date(today.year + rng.randint(*SPONSOR_YEARS), 6, 30),
        )
        for name in chosen
    )
    finances = ClubFinances(
        balance=rng.randint(*archetype.balance_m) * MILLION,
        wage_budget_weekly=wage_budget_weekly(income, archetype, rng.fork("wages")),
        transfer_budget=rng.randint(*archetype.transfer_budget_m) * MILLION,
        debt=debt,
        debt_interest_rate=rate,
        credit_limit=round(income * CREDIT_LIMIT_SHARE_OF_INCOME),
        sponsor_deals=deals,
        broadcast_share=round(income * BROADCAST_SHARE_OF_INCOME),
        last_reconciled_on=today,
    )
    return finances, income


def opening_entry(ids: IdMint, club_id: ClubId, balance: Money, today: dt.date) -> LedgerEntry:
    """The single opening-balance entry that makes ``balance == sum(ledger)`` true from day zero."""
    return LedgerEntry(
        id=Id(ids.next("ledger")),
        club_id=club_id,
        date=today,
        category=LedgerCategory.OTHER,
        amount=balance,
        memo_key="opening_balance",
    )
