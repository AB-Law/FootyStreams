"""Pure market-value formula from CA, PA, age, reputation and contract length."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from footystreams.domain.player import Player
from footystreams.domain.types import AbilityScore, Attribute, Money, Reputation

# Named constants — first-cut curve; M2 seeding may recalibrate against targets.
BASE_VALUE_CR = 50_000
CA_WEIGHT = 1.0
PA_WEIGHT = 0.45
REPUTATION_WEIGHT = 0.25
AGE_PEAK_DEFAULT = 27
AGE_PEAK_MIN = 24
AGE_PEAK_MAX = 31
AGE_YOUNG_SLOPE = 0.04
AGE_OLD_SLOPE = 0.06
HIGH_PA_THRESHOLD = 80
# Longer remaining term raises fee (asset security / harder free entry).
CONTRACT_YEAR_BONUS = 0.05
MAX_CONTRACT_YEARS = 10
# Peak-age shifts from player traits (± years around AGE_PEAK_DEFAULT).
FITNESS_PEAK_SPAN = 2.0
DETERMINATION_PEAK_SPAN = 1.0
INJURY_PEAK_SPAN = 1.5
ATTR_MIDPOINT = 50
WAGE_FACTOR = 0.20
DAYS_PER_YEAR = 365.25


@dataclass(frozen=True, slots=True)
class MarketValueInputs:
    """Scalar inputs to ``market_value`` (keeps the formula arg list small)."""

    ability_current: AbilityScore
    ability_potential: AbilityScore
    age: int
    reputation: Reputation
    contract_years_left: float
    peak_age: float = AGE_PEAK_DEFAULT


def compute_peak_age(
    *,
    natural_fitness: Attribute,
    determination: Attribute,
    injury_proneness: Attribute,
) -> float:
    """Per-player peak age for valuation and (later) development curves.

    High natural fitness / determination push the peak later and imply a
    longer plateau (Mbappé-like). High injury proneness pulls the peak
    earlier (early-wear careers). Motivation is not a separate player
    attribute yet — ``determination`` is the stand-in until M2/M10.
    """
    fitness_shift = (natural_fitness - ATTR_MIDPOINT) / ATTR_MIDPOINT * FITNESS_PEAK_SPAN
    grit_shift = (determination - ATTR_MIDPOINT) / ATTR_MIDPOINT * DETERMINATION_PEAK_SPAN
    injury_shift = (ATTR_MIDPOINT - injury_proneness) / ATTR_MIDPOINT * INJURY_PEAK_SPAN
    peak = AGE_PEAK_DEFAULT + fitness_shift + grit_shift + injury_shift
    return max(AGE_PEAK_MIN, min(AGE_PEAK_MAX, peak))


def market_value(inputs: MarketValueInputs) -> Money:
    """Deterministic crown valuation from ability, age, reputation and contract.

    Monotonic in CA, PA, reputation and remaining contract years when other
    inputs are held fixed. Younger age raises value for high-PA players
    (metamorphic property), not as a global age monotonic claim across all ages.
    Set ``inputs.peak_age`` from ``compute_peak_age`` for per-player curves.
    """
    ability_term = CA_WEIGHT * inputs.ability_current + PA_WEIGHT * inputs.ability_potential
    reputation_term = REPUTATION_WEIGHT * inputs.reputation
    age_factor = _age_factor(inputs.age, inputs.ability_potential, inputs.peak_age)
    years = max(0.0, min(float(inputs.contract_years_left), float(MAX_CONTRACT_YEARS)))
    contract_factor = 1.0 + CONTRACT_YEAR_BONUS * years
    raw = BASE_VALUE_CR * (ability_term + reputation_term) * age_factor * contract_factor
    return max(0, round(raw))


def _age_factor(age: int, ability_potential: AbilityScore, peak_age: float) -> float:
    if age <= peak_age:
        youth_boost = 1.0 + AGE_YOUNG_SLOPE * (peak_age - age)
        if ability_potential >= HIGH_PA_THRESHOLD:
            return youth_boost
        return 1.0 + 0.5 * AGE_YOUNG_SLOPE * (peak_age - age)
    return max(0.35, 1.0 - AGE_OLD_SLOPE * (age - peak_age))


def wage_from_value(value: Money) -> Money:
    """Weekly wage for a market value (sub-linear: stars earn more but not proportionally).

    Wages scale with ``value ** 0.75``, computed as ``sqrt(value) * sqrt(sqrt(value))`` so the
    result uses only correctly-rounded IEEE operations and is identical on every platform.
    """
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
