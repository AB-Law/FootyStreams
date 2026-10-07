"""Shared inputs for the people generators: tables, names, ids, geography and the world date."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from footystreams.domain.rng import WorldRng
from footystreams.domain.types import GameDate, NationId
from footystreams.domain.world import City, Nation
from footystreams.seed.ids import IdMint
from footystreams.seed.names.book import NameBook
from footystreams.seed.static.tables import StaticTables

HOME_NATIONALITY_SHARE = 0.70
HOME_REGION_SHARE = 0.75  # of home-nation players, how many come from the club's own region


@dataclass(frozen=True, slots=True)
class Geography:
    """Nations and cities people are born in; ``cities`` is grouped by nation."""

    nations: tuple[Nation, ...]
    cities: Mapping[NationId, tuple[City, ...]]

    @property
    def home(self) -> Nation:
        """The home nation (Valmere)."""
        return next(nation for nation in self.nations if nation.is_home)

    @property
    def foreign(self) -> tuple[Nation, ...]:
        """All other nations, in id order."""
        return tuple(sorted((n for n in self.nations if not n.is_home), key=lambda n: n.id))

    def regions(self) -> tuple[str, ...]:
        """Sorted region (name-culture) keys of the home nation's cities."""
        return tuple(sorted({city.region for city in self.cities[self.home.id] if city.region}))

    def pick_city(self, rng: WorldRng, nation_id: NationId, region: str | None = None) -> City:
        """A city of the nation (of the region, if given), weighted by population."""
        candidates = [
            city for city in self.cities[nation_id] if region is None or city.region == region
        ] or list(self.cities[nation_id])
        weights = {city.id: float(max(city.population, 1)) for city in candidates}
        chosen = rng.choice_weighted(weights)
        return next(city for city in candidates if city.id == chosen)


@dataclass(slots=True)
class GenerationContext:
    """Everything a person generator reads or advances (names and ids are stateful)."""

    tables: StaticTables
    names: NameBook
    ids: IdMint
    geography: Geography
    today: GameDate
