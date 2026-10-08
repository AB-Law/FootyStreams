"""League health numbers read off a database: ability, age, squads and money over the years.

Used by the long-run statistical test and the ``league`` report; pure functions of the rows.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.transfer import OUTSIDE_WORLD


@dataclass(frozen=True, slots=True)
class Health:
    """One moment in the life of the league."""

    mean_ability: float
    mean_age: float
    seniors: int
    youth: int
    free_agents: int
    clubs_in_debt: int


def _in_league(player: Player) -> bool:
    """True when the player is not under contract to the synthetic outside club."""
    return player.contract is None or player.contract.club_id != OUTSIDE_WORLD


def health(players: Sequence[Player], clubs: Sequence[Club], today: dt.date) -> Health:
    """Mean senior ability and age, head counts and how many clubs are overdrawn.

    The ``OUTSIDE_WORLD`` counterparty and its supply are excluded so the numbers describe
    the league, not the transfer market's filler pool.
    """
    league = [club for club in clubs if club.id != OUTSIDE_WORLD]
    seniors = [
        p for p in players if p.status is PlayerStatus.ACTIVE and not p.is_youth and _in_league(p)
    ]
    count = max(1, len(seniors))
    return Health(
        mean_ability=sum(p.ability_current for p in seniors) / count,
        mean_age=sum(p.age_on(today) for p in seniors) / count,
        seniors=len(seniors),
        youth=sum(
            1 for p in players if p.status is PlayerStatus.ACTIVE and p.is_youth and _in_league(p)
        ),
        free_agents=sum(1 for p in players if p.status is PlayerStatus.FREE_AGENT),
        clubs_in_debt=sum(
            1 for club in league if club.finances.balance < -club.finances.credit_limit
        ),
    )
