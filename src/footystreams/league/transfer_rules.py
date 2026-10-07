"""The rules of a deal: desire, opening bid, reservation price, rounds, medicals, affordability.

Pure functions of a stream and the configuration. The market code composes them; each one can be
tested on its own (docs/design/07 section 6.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.contract import SquadRole
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Money
from footystreams.league.needs import Need
from footystreams.league.scouting import Perception
from footystreams.league.transfer_config import MedicalConfig, NeedsConfig, ValuationConfig

PROPENSITY_SCALE = 100.0
UNIT_MAX = 1.0
BASE_STUBBORNNESS = 1.0


@dataclass(frozen=True, slots=True)
class FeeTalks:
    """Everything a fee negotiation needs."""

    market_value: Money
    desire: float
    urgency: float
    reservation: Money


@dataclass(frozen=True, slots=True)
class FeeAgreed:
    """A fee both clubs accept, and the round it was struck in."""

    fee: Money
    round: int


def desire(perception: Perception, need: Need, age: int, config: ValuationConfig) -> float:
    """0..1: how much the club wants this player for this need, from what it believes of him."""
    base = (perception.ability - need.min_quality) / config.desire_scale + 0.5
    if age <= config.youth_age:
        base += (
            config.youth_weight * (perception.potential - perception.ability) / config.desire_scale
        )
    return max(0.0, min(UNIT_MAX, base))


def opening_bid(talks: FeeTalks, config: ValuationConfig, rng: WorldRng) -> Money:
    """Market value x (1 + desire x w + urgency x w + noise)."""
    premium = config.desire_weight * talks.desire + config.urgency_weight * talks.urgency
    noise = rng.normal(0.0, config.bid_noise)
    return max(0, round(talks.market_value * (1.0 + premium + noise)))


def reservation_price(
    market_value: Money,
    role: SquadRole,
    ask: Money | None,
    context: tuple[ValuationConfig, bool],
) -> Money:
    """What the seller wants: value x how attached he is to the role, or the asking price.

    ``context`` is (config, seller in financial trouble); trouble lowers the price.
    """
    config, distressed = context
    stubborn = config.role_stubbornness.get(role.value, BASE_STUBBORNNESS)
    price = market_value * stubborn * ((1.0 - config.financial_discount) if distressed else 1.0)
    return round(max(price, ask or 0))


def negotiate_fee(talks: FeeTalks, config: ValuationConfig, rng: WorldRng) -> FeeAgreed | None:
    """Up to ``rounds`` bids, rising from the opening bid to the buyer's ceiling.

    The seller accepts the first bid at or above his reservation price times a factor drawn once
    between the configured floor and 1.0. The buyer's bid never passes his ceiling.
    """
    opening = opening_bid(talks, config, rng.fork("opening"))
    ceiling = round(opening * (1.0 + config.ceiling_margin))
    threshold = talks.reservation * rng.fork("seller").uniform(config.reservation_floor, UNIT_MAX)
    for number in range(1, config.rounds + 1):
        step = min(UNIT_MAX, config.round_concession * (number - 1))
        bid = round(opening + (ceiling - opening) * step)
        if bid >= threshold:
            return FeeAgreed(fee=bid, round=number)
    return None


def medical_passes(player: Player, config: MedicalConfig, rng: WorldRng) -> bool:
    """False with a chance that grows with injury proneness and is large for an injured player."""
    chance = (
        config.base_failure
        + config.proneness_weight * player.hidden.injury_proneness / PROPENSITY_SCALE
    )
    if player.current_injury is not None:
        chance += config.injured_failure
    return not rng.bernoulli(min(UNIT_MAX, chance))


def can_afford(
    club: Club,
    deal: tuple[Money, Money, Money],
    config: NeedsConfig,
    *,
    urgent: bool,
) -> bool:
    """Whether the club may spend this: ``deal`` is (fee, new wage, current weekly wage bill).

    The fee must fit the transfer budget (and one deal may use only a share of it unless the club
    is desperate), the club may not go past its overdraft, and the wage bill stays within headroom.
    """
    fee, wage, bill = deal
    finances = club.finances
    share = UNIT_MAX if urgent else config.max_signing_share
    fits_budget = fee <= finances.transfer_budget * share
    fits_overdraft = finances.balance - fee >= -finances.credit_limit
    fits_wages = bill + wage <= finances.wage_budget_weekly * config.wage_headroom
    return fits_budget and fits_overdraft and fits_wages
