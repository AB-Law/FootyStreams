"""``ProspectFactory`` over the seed generators: new academy players and journeymen mid-run.

The league layer asks for players by request (position, age, ability, club); this adapter draws
them with the same generators the world was built with. Names stay unique against the people
already in the world; ids come from the request key, so the same request always gives the same id.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Sequence

from footystreams.domain.ids import IdMint, derive_id
from footystreams.domain.player import Player
from footystreams.domain.prospects import ProspectRequest
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Id
from footystreams.seed.names.book import NameBook, NameBookState
from footystreams.seed.players.context import GenerationContext, Geography
from footystreams.seed.players.generator import PlayerSpec, generate_player
from footystreams.seed.static.tables import StaticTables


class SeedProspectFactory:
    """Creates players for the league layer with the seed generators."""

    def __init__(self, tables: StaticTables, geography: Geography) -> None:
        """Create the factory over the static tables and the world's geography."""
        self._tables = tables
        self._geography = geography

    def create(
        self,
        requests: Sequence[ProspectRequest],
        existing: Sequence[Player],
        context: tuple[dt.date, WorldRng],
    ) -> list[Player]:
        """One new player per request, born relative to the date; names avoid ``existing``."""
        today, rng = context
        names = NameBook.from_static()
        names.restore(
            NameBookState(
                known_as=frozenset(p.known_as for p in existing),
                surnames=Counter(p.last_name for p in existing),
                places=frozenset(),
            )
        )
        generation = GenerationContext(self._tables, names, IdMint(), self._geography, today)
        return [self._one(request, generation, rng.fork(request.key)) for request in requests]

    def _one(self, request: ProspectRequest, context: GenerationContext, rng: WorldRng) -> Player:
        spec = PlayerSpec(
            position=request.position,
            age=request.age,
            target_ability=request.ability,
            club_id=ClubId(request.club_id) if request.club_id else None,
            region=request.region,
            club_reputation=request.club_reputation,
            youth=request.youth,
            potential_bonus=request.potential_bonus,
        )
        player = generate_player(spec, context, rng)
        return player.model_copy(update={"id": Id(derive_id("player", request.key))})
