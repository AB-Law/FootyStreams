"""Market value, wages and contracts for generated players.

Wages scale with ``value ** 0.75``, computed as ``sqrt(value) * sqrt(sqrt(value))`` so the result
uses only correctly-rounded IEEE operations and is identical on every platform.
"""

from __future__ import annotations

import datetime as dt
import math

from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Money, Position
from footystreams.domain.valuation import MarketValueInputs, compute_peak_age, market_value

CONTRACT_END_MONTH, CONTRACT_END_DAY = 6, 30
REMAINING_YEARS = {1: 0.28, 2: 0.27, 3: 0.22, 4: 0.15, 5: 0.08}
YOUTH_CONTRACT_YEARS = 3
MAX_ELAPSED_YEARS = 2
WAGE_FACTOR = 0.20
APPEARANCE_BONUS_SHARE = 0.05
GOAL_BONUS_SHARE = 0.10
CLEAN_SHEET_BONUS_SHARE = 0.08
RELEASE_CLAUSE_CHANCE = 0.05
RELEASE_CLAUSE_MULTIPLE = 2.5
SELL_ON_CHANCE = 0.05
SELL_ON_RANGE = (0.10, 0.20)
ATTACKERS = frozenset({Position.ST, Position.SS, Position.RW, Position.LW, Position.AM})
DEFENDERS = frozenset({Position.GK, Position.CB, Position.RB, Position.LB, Position.DM})
DAYS_PER_YEAR = 365.25


def wage_from_value(value: Money) -> Money:
    """Weekly wage for a market value (sub-linear: stars earn more but not proportionally)."""
    root = math.sqrt(max(value, 0))
    return round(WAGE_FACTOR * root * math.sqrt(root))


def market_value_of(player: Player, today: dt.date) -> Money:
    """Crown valuation of a player on ``today`` (uses his contract term when he has one)."""
    years_left = 0.0
    if player.contract is not None:
        years_left = max(0.0, (player.contract.end - today).days / DAYS_PER_YEAR)
    peak = compute_peak_age(
        natural_fitness=player.physical.natural_fitness,
        determination=player.mental.determination,
        injury_proneness=player.hidden.injury_proneness,
    )
    return market_value(
        MarketValueInputs(
            ability_current=player.ability_current,
            ability_potential=player.ability_potential,
            age=player.age_on(today),
            reputation=player.reputation,
            contract_years_left=years_left,
            peak_age=peak,
        )
    )


def contract_for(
    rng: WorldRng,
    player: Player,
    club_id: ClubId,
    role: SquadRole,
    today: dt.date,
) -> Contract:
    """A staggered contract: remaining term drawn so about a quarter expire each summer."""
    remaining = YOUTH_CONTRACT_YEARS if player.is_youth else rng.choice_weighted(REMAINING_YEARS)
    end = dt.date(today.year + remaining, CONTRACT_END_MONTH, CONTRACT_END_DAY)
    elapsed = 0 if player.is_youth else rng.randint(0, MAX_ELAPSED_YEARS)
    start = dt.date(end.year - remaining - elapsed, 7, 1)
    wage = wage_from_value(market_value_of(player, today))
    position = player.primary_position
    return Contract(
        club_id=club_id,
        start=start,
        end=end,
        wage_weekly=wage,
        appearance_bonus=round(wage * APPEARANCE_BONUS_SHARE),
        goal_bonus=round(wage * GOAL_BONUS_SHARE) if position in ATTACKERS else 0,
        clean_sheet_bonus=round(wage * CLEAN_SHEET_BONUS_SHARE) if position in DEFENDERS else 0,
        release_clause=_release_clause(rng, player, today),
        sell_on_pct=_sell_on(rng, player),
        squad_role=role,
    )


def _release_clause(rng: WorldRng, player: Player, today: dt.date) -> Money | None:
    if not rng.bernoulli(RELEASE_CLAUSE_CHANCE):
        return None
    return round(market_value_of(player, today) * RELEASE_CLAUSE_MULTIPLE)


def _sell_on(rng: WorldRng, player: Player) -> float:
    return rng.uniform(*SELL_ON_RANGE) if player.is_youth and rng.bernoulli(SELL_ON_CHANCE) else 0.0
