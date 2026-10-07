"""Pure market-value formula from CA, PA, age, reputation and contract length."""

from __future__ import annotations

from footystreams.domain.types import AbilityScore, Money, Reputation

# Named constants — first-cut curve; M2 seeding may recalibrate against targets.
BASE_VALUE_CR = 50_000
CA_WEIGHT = 1.0
PA_WEIGHT = 0.45
REPUTATION_WEIGHT = 0.25
AGE_PEAK = 27
AGE_YOUNG_SLOPE = 0.04
AGE_OLD_SLOPE = 0.06
HIGH_PA_THRESHOLD = 80
CONTRACT_YEAR_BONUS = 0.05
MAX_CONTRACT_YEARS = 5


def market_value(
    *,
    ability_current: AbilityScore,
    ability_potential: AbilityScore,
    age: int,
    reputation: Reputation,
    contract_years_left: float,
) -> Money:
    """Deterministic crown valuation from ability, age, reputation and contract.

    Monotonic in CA, PA and reputation when other inputs are held fixed.
    Younger age raises value for high-PA players (metamorphic property), not
    as a global monotonic claim across all ages.
    """
    ability_term = CA_WEIGHT * ability_current + PA_WEIGHT * ability_potential
    reputation_term = REPUTATION_WEIGHT * reputation
    age_factor = _age_factor(age, ability_potential)
    years = max(0.0, min(float(contract_years_left), float(MAX_CONTRACT_YEARS)))
    contract_factor = 1.0 + CONTRACT_YEAR_BONUS * years
    raw = BASE_VALUE_CR * (ability_term + reputation_term) * age_factor * contract_factor
    return max(0, round(raw))


def _age_factor(age: int, ability_potential: AbilityScore) -> float:
    if age <= AGE_PEAK:
        youth_boost = 1.0 + AGE_YOUNG_SLOPE * (AGE_PEAK - age)
        if ability_potential >= HIGH_PA_THRESHOLD:
            return youth_boost
        return 1.0 + 0.5 * AGE_YOUNG_SLOPE * (AGE_PEAK - age)
    return max(0.35, 1.0 - AGE_OLD_SLOPE * (age - AGE_PEAK))
