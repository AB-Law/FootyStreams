"""Named stubs for clubs outside the Valmere Premier League (career-history employers)."""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId
from footystreams.domain.world import WIDER_WORLD_CLUB_COUNT, WIDER_WORLD_PREFIX, WiderClub
from footystreams.seed.clubs.archetypes import ClubTables
from footystreams.seed.names.book import NameBook

NICKNAMES = (
    "the Wanderers",
    "the Mariners",
    "the Oaks",
    "the Magpies",
    "the Irons",
    "the Swans",
    "the Bees",
    "the Cottagers",
    "the Tricky Trees",
    "the Clarets",
    "the Potters",
    "the Tykes",
    "the Owls",
    "the Blades",
    "the Rams",
    "the Robins",
    "the Canaries",
    "the Cherries",
    "the Seagulls",
    "the Hornets",
)
REGIONS = ("highland", "coastal", "rivervale", "portside", "borderlands", "isles")


def generate_wider_clubs(
    rng: WorldRng,
    names: NameBook,
    tables: ClubTables,
    taken_names: Sequence[str],
) -> tuple[WiderClub, ...]:
    """Forty speakable clubs with fixed ``clb_wdNNN`` ids, avoiding league club names."""
    blocked = {name.casefold() for name in taken_names}
    used_suffixes: set[str] = set()
    used_nicknames: set[str] = set()
    clubs: list[WiderClub] = []
    for index in range(1, WIDER_WORLD_CLUB_COUNT + 1):
        stream = rng.fork(f"wider:{index:03d}")
        region = stream.choice(list(REGIONS))
        city = _unique_place(names, stream.fork("place"), region, blocked)
        free_suffixes = [s for s in tables.club_suffixes if s not in used_suffixes]
        suffix = stream.choice(free_suffixes or list(tables.club_suffixes))
        used_suffixes.add(suffix)
        free_nicks = [n for n in NICKNAMES if n not in used_nicknames]
        nickname = stream.choice(free_nicks or list(NICKNAMES))
        used_nicknames.add(nickname)
        name = f"{city} {suffix}"
        blocked.add(name.casefold())
        clubs.append(
            WiderClub(
                id=ClubId(f"{WIDER_WORLD_PREFIX}{index:03d}"),
                name=name,
                short_name=city,
                nickname=nickname,
                city=city,
                region=region,
            )
        )
    return tuple(clubs)


def _unique_place(names: NameBook, rng: WorldRng, region: str, blocked: set[str]) -> str:
    """A place name that is not already used as a league or wider-world club city."""
    for _ in range(80):
        place = names.place(rng, region)
        if place.casefold() not in blocked:
            blocked.add(place.casefold())
            return place
    msg = f"could not draw a unique wider-world place in region {region!r}"
    raise RuntimeError(msg)
