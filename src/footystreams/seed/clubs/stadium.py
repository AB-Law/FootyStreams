"""Stadium and fanbase for a club archetype."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.club import Fanbase
from footystreams.domain.rng import WorldRng
from footystreams.domain.stadium import HomeAdvantageFactors, Pitch, PitchSurface, Stadium
from footystreams.domain.world import City
from footystreams.seed.clubs.archetypes import ClubArchetype
from footystreams.seed.names.book import NameBook

DEFAULT_CULTURE = "highland"
HIGHLAND_ALTITUDE = (300, 700)
LOWLAND_ALTITUDE = (0, 150)
FAMILIARITY_RANGE = (0.4, 0.7)
TRAVEL_RANGE = (0.3, 0.7)
WEIGHT_NOISE = 0.05
CAULDRON_ATMOSPHERE = 0.80
CAULDRON_NAMES = ("The Cauldron", "The Bear Pit", "The Furnace")
TICKET_BASE = 15
TICKET_PER_REPUTATION = 0.5
THOUSAND = 1_000
TRADITIONS = (
    "the pre-match anthem", "the bell at half time", "scarves aloft at kickoff",
    "the long-throw roar", "the drum corner", "the walk to the ground",
)  # fmt: skip
MAX_TRADITIONS = 3


def _unit(rng: WorldRng, bounds: tuple[float, float]) -> float:
    return rng.uniform(*bounds)


@dataclass(frozen=True, slots=True)
class StadiumSite:
    """Where and for whom a stadium is built."""

    city: City
    names: NameBook
    suffixes: tuple[str, ...]
    reputation: int


def make_stadium(rng: WorldRng, archetype: ClubArchetype, site: StadiumSite) -> Stadium:
    """A ground whose size, surface and atmosphere follow the archetype, named after a district."""
    spec = archetype.stadium
    city = site.city
    atmosphere = _unit(rng, spec.atmosphere)
    proximity = _unit(rng, spec.proximity)
    district = site.names.place(rng.fork("name"), city.region or DEFAULT_CULTURE)
    altitude = LOWLAND_ALTITUDE if city.climate != "highland" else HIGHLAND_ALTITUDE
    return Stadium(
        name=f"{district} {rng.choice(site.suffixes)}",
        nickname=rng.choice(CAULDRON_NAMES) if atmosphere >= CAULDRON_ATMOSPHERE else "",
        capacity=rng.randint(*spec.capacity),
        pitch=Pitch(
            length_m=rng.randint(*spec.length),
            width_m=rng.randint(*spec.width),
            quality=_unit(rng, spec.pitch_quality),
            surface=PitchSurface(spec.surface),
            drainage=rng.uniform(0.3, 0.9),
        ),
        atmosphere=atmosphere,
        proximity=proximity,
        altitude_m=rng.randint(*altitude),
        home_advantage=HomeAdvantageFactors(
            crowd_weight=rng.truncated_normal(atmosphere, WEIGHT_NOISE, 0.0, 1.0),
            referee_pressure_weight=rng.truncated_normal(proximity, WEIGHT_NOISE, 0.0, 1.0),
            familiarity_weight=_unit(rng, FAMILIARITY_RANGE),
            travel_weight=_unit(rng, TRAVEL_RANGE),
        ),
        ticket_price_base=round(
            TICKET_BASE + TICKET_PER_REPUTATION * rng.randint(*archetype.reputation)
        ),
    )


def make_fanbase(rng: WorldRng, archetype: ClubArchetype) -> Fanbase:
    """Support profile drawn from the archetype's ranges."""
    spec = archetype.fanbase
    return Fanbase(
        size=rng.randint(*spec.size_k) * THOUSAND,
        passion=_unit(rng, spec.passion),
        toxicity=_unit(rng, spec.toxicity),
        fickleness=_unit(rng, spec.fickleness),
        away_following=_unit(rng, spec.away_following),
        traditions=tuple(rng.shuffled(TRADITIONS)[: rng.randint(1, MAX_TRADITIONS)]),
    )
