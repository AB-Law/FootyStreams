"""The request/response contract for creating new players during a run.

Lives in domain because the league layer asks for players and the seed layer (which owns names,
geography and archetypes) builds them, and neither may import the other.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Position


@dataclass(frozen=True, slots=True)
class ProspectRequest:
    """One player to create."""

    key: str  # unique and stable for the request, e.g. "2032:clb_00001:3"; seeds his id
    position: Position
    age: int
    ability: int
    potential_bonus: int
    region: str
    club_reputation: int
    club_id: ClubId | None  # None for a free agent
    youth: bool


class ProspectFactory(Protocol):
    """Creates players for requests; ``existing`` are the people whose names are taken."""

    def create(
        self,
        requests: Sequence[ProspectRequest],
        existing: Sequence[Player],
        context: tuple[dt.date, WorldRng],
    ) -> list[Player]:
        """One new player per request, in order; ids must depend only on the request key.

        ``context`` is (the in-world date the players are created on, the random stream).
        """
