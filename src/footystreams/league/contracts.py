"""Contract talks: how willing a player is, and a club-player negotiation of up to three rounds.

Pure. The same willingness rule serves renewals and transfers (docs/design/07 sections 5 and 6):
it weighs the wage against the market wage, the club's standing against the player's ambition,
his mood, and his loyalty to a club he already plays for.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.contract import SquadRole
from footystreams.domain.ids import derive_id
from footystreams.domain.mood import ModifierVisibility, WorldEvent
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind, EntityRef, Id, Money
from footystreams.domain.valuation import market_value_of, wage_from_value
from footystreams.league.squad import released
from footystreams.league.transfer_config import RenewalConfig, TermsConfig

TRAIT_MIDPOINT = 50.0
TRAIT_SPAN = 50.0
REPUTATION_SPAN = 50.0
UNIT_CENTRE = 0.5


@dataclass(frozen=True, slots=True)
class Proposal:
    """A contract on the table."""

    club_reputation: int
    wage: Money
    current_club: bool  # the player already plays for the club
    free_agent: bool = False


@dataclass(frozen=True, slots=True)
class Agreed:
    """The terms a negotiation ended with."""

    wage: Money
    length_years: int
    round: int


def market_wage(player: Player, today: dt.date) -> Money:
    """What the market pays a player of his value."""
    return wage_from_value(market_value_of(player, today))


def _lean(value: int) -> float:
    return (value - TRAIT_MIDPOINT) / TRAIT_SPAN


def willingness(
    player: Player, proposal: Proposal, wage_market: Money, terms: TermsConfig
) -> float:
    """Positive when the player would sign: wage premium, club standing, mood, loyalty."""
    premium = proposal.wage / wage_market - 1.0 if wage_market else 0.0
    standing = (proposal.club_reputation - player.reputation) / REPUTATION_SPAN
    score = terms.wage_weight * premium
    score += terms.ambition_weight * _lean(player.personality.ambition) * standing
    score += terms.mood_weight * (player.morale - UNIT_CENTRE) * 2.0
    if proposal.free_agent:
        score += terms.free_agent_bonus
    return score


def loyalty_bonus(player: Player, proposal: Proposal, weight: float) -> float:
    """Extra willingness to stay at the current club."""
    return weight * max(0.0, _lean(player.personality.loyalty)) if proposal.current_club else 0.0


def negotiate(
    player: Player,
    club: tuple[int, float],
    config: tuple[TermsConfig, RenewalConfig],
    context: tuple[dt.date, WorldRng, bool],
) -> Agreed | None:
    """Up to ``len(wage_rounds)`` rounds: each offers a higher multiple of the market wage.

    ``club`` is (the club's reputation, its affordability scale for wages); ``context`` is
    (today, stream, whether the player already plays for the club).
    """
    terms, renewal = config
    reputation, scale = club
    today, rng, current = context
    wage_market = market_wage(player, today)
    for number, multiple in enumerate(terms.wage_rounds, start=1):
        proposal = Proposal(reputation, round(wage_market * multiple * scale), current)
        score = willingness(player, proposal, wage_market, terms) + loyalty_bonus(
            player, proposal, renewal.loyalty_weight
        )
        if score >= terms.threshold:
            years = rng.fork("length").randint(*terms.length_years)
            return Agreed(wage=proposal.wage, length_years=years, round=number)
    return None


def club_wants(
    player: Player,
    peers: Sequence[Player],
    role: SquadRole,
    context: tuple[RenewalConfig, dt.date],
) -> bool:
    """Whether a club renews: young enough and not far below his position's median."""
    config, today = context
    if player.age_on(today) > config.max_age:
        return False
    abilities = sorted(
        p.ability_current for p in peers if p.primary_position is player.primary_position
    )
    median = abilities[len(abilities) // 2] if abilities else player.ability_current
    return player.ability_current >= median - config.role_tolerance[role.value]


@dataclass(frozen=True, slots=True)
class Expiry:
    """What contract expiry changes."""

    players: tuple[Player, ...]
    events: tuple[WorldEvent, ...]
    deletions: tuple[tuple[str, str], ...]


def expire_contracts(players: Sequence[Player], today: dt.date) -> Expiry:
    """Players whose contract ended before ``today`` become free agents."""
    gone: list[Player] = []
    events: list[WorldEvent] = []
    deletions: list[tuple[str, str]] = []
    for player in sorted(players, key=lambda item: item.id):
        contract = player.contract
        if contract is None or contract.end >= today:
            continue
        gone.append(released(player))
        deletions.append(("squad_entries", f"{contract.club_id}:{player.id}"))
        events.append(
            WorldEvent(
                id=Id(derive_id("world_event", player.id, today.isoformat(), "contract_expired")),
                date=today,
                kind="contract_expired",
                participants=(
                    EntityRef(kind=EntityKind.PLAYER, id=Id(player.id)),
                    EntityRef(kind=EntityKind.CLUB, id=Id(contract.club_id)),
                ),
                visibility=ModifierVisibility.PUBLIC,
                origin="rule",
            )
        )
    return Expiry(tuple(gone), tuple(events), tuple(deletions))
