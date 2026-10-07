"""Nations and cities: the home nation Valmere with six regions, and eight foreign nations."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.rng import WorldRng
from footystreams.domain.types import CityId, NationId
from footystreams.domain.world import City, Nation
from footystreams.seed.ids import IdMint
from footystreams.seed.names.book import NameBook
from footystreams.seed.players.context import Geography

HOME_NATION_ID = NationId("nat_valmere")
HOME_NATION_NAME = "Valmere"
HOME_DEMONYM = "Valmerian"
DEFAULT_REGION_CULTURE = "highland"
CITIES_PER_REGION = 3
CITIES_PER_FOREIGN_NATION = 3
CITY_POPULATION_RANGE = (40_000, 900_000)
REGION_CLIMATE = {
    "highland": "highland",
    "coastal": "coastal",
    "rivervale": "temperate",
    "portside": "warm",
    "borderlands": "continental",
    "isles": "coastal",
}
FOREIGN_CLIMATES = ("temperate", "continental", "warm", "coastal")


@dataclass(frozen=True, slots=True)
class _CityMaker:
    """Mints cities with unique names; names and ids carry the uniqueness state."""

    names: NameBook
    ids: IdMint

    def make(self, rng: WorldRng, nation: Nation, region: str, climate: str) -> City:
        return City(
            id=CityId(self.ids.next("city")),
            name=self.names.place(rng, region or nation.name_culture),
            nation_id=nation.id,
            region=region,
            population=rng.randint(*CITY_POPULATION_RANGE),
            climate=climate,
        )


def generate_geography(rng: WorldRng, names: NameBook, ids: IdMint) -> Geography:
    """Home nation with its regional cities, plus a foreign nation per foreign name culture."""
    home = Nation(
        id=HOME_NATION_ID,
        name=HOME_NATION_NAME,
        demonym=HOME_DEMONYM,
        is_home=True,
        name_culture=DEFAULT_REGION_CULTURE,
    )
    maker = _CityMaker(names, ids)
    nations = [home]
    cities: dict[NationId, tuple[City, ...]] = {}
    home_rng = rng.fork("home-cities")
    cities[home.id] = tuple(
        maker.make(home_rng, home, region, REGION_CLIMATE[region])
        for region in names.culture_keys("region")
        for _ in range(CITIES_PER_REGION)
    )
    for index, key in enumerate(names.culture_keys("nation")):
        culture = names.culture(key)
        nation = Nation(
            id=NationId(f"nat_{key}"),
            name=key.capitalize(),
            demonym=culture.label,
            name_culture=key,
        )
        nations.append(nation)
        foreign_rng = rng.fork(f"cities:{key}")
        climate = FOREIGN_CLIMATES[index % len(FOREIGN_CLIMATES)]
        cities[nation.id] = tuple(
            maker.make(foreign_rng, nation, "", climate) for _ in range(CITIES_PER_FOREIGN_NATION)
        )
    return Geography(nations=tuple(nations), cities=cities)
