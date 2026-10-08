"""A club's year-end: reputation and support follow the finish, money is reset for the next year."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.finance import SponsorDeal
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId
from footystreams.league.config import FinanceConfig
from footystreams.league.development_config import RolloverConfig
from footystreams.league.finance import income_estimate

REPUTATION_MAX = 100
CONTRACT_END = (6, 30)


def expected_places(clubs: Sequence[Club]) -> dict[ClubId, int]:
    """Where each club is expected to finish: by reputation, best first (ties by id)."""
    ranked = sorted(clubs, key=lambda club: (-club.club_reputation, club.id))
    return {club.id: place for place, club in enumerate(ranked, start=1)}


def performance(expected: int, final: int, clubs: int) -> float:
    """How far above (positive) or below (negative) expectation, as a share of the table."""
    return (expected - final) / max(1, clubs - 1)


def update_standing(club: Club, score: float, clubs: int, config: RolloverConfig) -> Club:
    """Reputation, fan base and board confidence follow the result against expectation."""
    step = round(config.reputation_step * score * (clubs - 1))
    change = max(-config.reputation_max_change, min(config.reputation_max_change, step))
    fanbase = club.fanbase.model_copy(
        update={"size": max(0, round(club.fanbase.size * (1 + config.fanbase_drift * score)))}
    )
    confidence = max(0.0, min(1.0, club.board.manager_confidence + config.confidence_step * score))
    return club.model_copy(
        update={
            "club_reputation": max(0, min(REPUTATION_MAX, club.club_reputation + change)),
            "fanbase": fanbase,
            "board": club.board.model_copy(update={"manager_confidence": round(confidence, 4)}),
        }
    )


def renew_sponsors(
    club: Club, today: dt.date, reputation_gain: int, context: tuple[RolloverConfig, WorldRng]
) -> tuple[SponsorDeal, ...]:
    """Deals that ended are renewed for 1-3 years, worth more when the club's standing rose."""
    config, rng = context
    deals = []
    for index, deal in enumerate(club.finances.sponsor_deals):
        if deal.ends_on > today:
            deals.append(deal)
            continue
        years = rng.fork(f"sponsor:{index}").randint(*config.sponsor_years)
        value = round(deal.annual_value * (1 + config.sponsor_reputation_growth * reputation_gain))
        deals.append(
            SponsorDeal(
                name=deal.name,
                annual_value=max(0, value),
                ends_on=dt.date(today.year + years, *CONTRACT_END),
            )
        )
    return tuple(deals)


def reset_budgets(club: Club, finance: FinanceConfig, config: RolloverConfig) -> Club:
    """Wage budget from the income estimate; transfer budget from the money in the bank."""
    income = income_estimate(club, finance)
    wage_budget = round(income * config.wage_budget_ratio / finance.weeks_per_year)
    transfer_budget = max(0, round(club.finances.balance * config.transfer_budget_share)) + round(
        income * config.transfer_budget_income_share
    )
    finances = club.finances.model_copy(
        update={"wage_budget_weekly": wage_budget, "transfer_budget": transfer_budget}
    )
    return club.model_copy(update={"finances": finances})
