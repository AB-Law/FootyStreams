"""League health numbers read off a database: ability, age, squads and money over the years.

Used by the long-run statistical test and the ``league`` report; pure functions of the rows.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.player import Player, PlayerStatus


@dataclass(frozen=True, slots=True)
class Health:
    """One moment in the life of the league."""

    mean_ability: float
    mean_age: float
    seniors: int
    youth: int
    free_agents: int
    clubs_in_debt: int


def health(players: Sequence[Player], clubs: Sequence[Club], today: dt.date) -> Health:
    """Mean senior ability and age, head counts and how many clubs are overdrawn."""
    seniors = [p for p in players if p.status is PlayerStatus.ACTIVE and not p.is_youth]
    count = max(1, len(seniors))
    return Health(
        mean_ability=sum(p.ability_current for p in seniors) / count,
        mean_age=sum(p.age_on(today) for p in seniors) / count,
        seniors=len(seniors),
        youth=sum(1 for p in players if p.status is PlayerStatus.ACTIVE and p.is_youth),
        free_agents=sum(1 for p in players if p.status is PlayerStatus.FREE_AGENT),
        clubs_in_debt=sum(
            1 for club in clubs if club.finances.balance < -club.finances.credit_limit
        ),
    )
