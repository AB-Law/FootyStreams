"""Club identity: city, name, three-letter code, colours, nickname, crest and founding year."""

from __future__ import annotations

from dataclasses import dataclass, field

from footystreams.domain.club import ClubColours, ClubLocation, KitPattern, KitSpec
from footystreams.domain.rng import WorldRng
from footystreams.domain.textfold import plain
from footystreams.domain.world import City
from footystreams.seed.clubs.archetypes import ClubArchetype, ClubTables, Palette

SHORT_CODE_LENGTH = 3
FALLBACK_LETTERS = "abcdefghijklmnopqrstuvwxyz"
NEUTRAL_AWAY = "#ffffff"


@dataclass(slots=True)
class IdentityRegistry:
    """What earlier clubs already took, so later clubs differ (mutable: it accumulates)."""

    cities: set[str] = field(default_factory=set)
    initials: set[str] = field(default_factory=set)
    suffixes: set[str] = field(default_factory=set)
    codes: set[str] = field(default_factory=set)
    nicknames: set[str] = field(default_factory=set)
    palettes: set[int] = field(default_factory=set)
    home_primaries: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class ClubIdentity:
    """The look-and-name part of a club."""

    name: str
    short_name: str
    short_code: str
    nickname: str
    colours: ClubColours
    crest_description: str
    founded_year: int
    location: ClubLocation
    city: City


def pick_city(remaining: list[City], percentile: float, taken_initials: set[str]) -> City:
    """The city at a population percentile, preferring a first letter no club has yet."""
    ranked = sorted(remaining, key=lambda city: (-city.population, city.id))
    target = round(percentile * (len(ranked) - 1))
    by_distance = sorted(range(len(ranked)), key=lambda index: (abs(index - target), index))
    for index in by_distance:
        if plain(ranked[index].name)[:1] not in taken_initials:
            return ranked[index]
    return ranked[target]


def short_code_for(name: str, taken: set[str]) -> str:
    """Three uppercase letters from the name, trying readable combinations before a fallback."""
    letters = plain(name)
    combos = [
        (0, 1, 2), (0, 1, 3), (0, 2, 3), (0, 1, 4), (0, 2, 4), (1, 2, 3), (0, 3, 4),
    ]  # fmt: skip
    for combo in combos:
        if max(combo) < len(letters):
            code = "".join(letters[i] for i in combo).upper()
            if code not in taken:
                return code
    for filler in FALLBACK_LETTERS:
        code = (letters[:2] + filler).upper()
        if len(code) == SHORT_CODE_LENGTH and code not in taken:
            return code
    msg = f"no free short code for {name!r}"
    raise ValueError(msg)


def _kit_colours(palette: Palette, other_home_primaries: set[str]) -> tuple[KitSpec, KitSpec]:
    away_choice = next(
        (
            colour
            for colour in (palette.secondary, palette.accent, NEUTRAL_AWAY)
            if colour not in other_home_primaries and colour != palette.primary
        ),
        NEUTRAL_AWAY,
    )
    home = KitSpec(pattern=KitPattern.SOLID, colours=(palette.primary, palette.secondary))
    away = KitSpec(pattern=KitPattern.SOLID, colours=(away_choice, palette.primary))
    return home, away


def pick_colours(
    rng: WorldRng, tables: ClubTables, registry: IdentityRegistry
) -> tuple[ClubColours, int]:
    """An unused palette, a home kit pattern and an away kit contrasting with every home kit."""
    free = [i for i in range(len(tables.palettes)) if i not in registry.palettes]
    index = rng.choice(free)
    palette = tables.palettes[index]
    home, away = _kit_colours(palette, registry.home_primaries)
    pattern = KitPattern(rng.choice_weighted(tables.kit_patterns))
    colours = ClubColours(
        primary=palette.primary,
        secondary=palette.secondary,
        accent=palette.accent,
        home_kit=home.model_copy(update={"pattern": pattern}),
        away_kit=away,
    )
    return colours, index


def make_identity(
    rng: WorldRng,
    tables: ClubTables,
    archetype: ClubArchetype,
    remaining_cities: list[City],
    registry: IdentityRegistry,
) -> ClubIdentity:
    """Choose city, name, code, colours, nickname and crest; records the choices in the registry."""
    city = pick_city(remaining_cities, archetype.city_percentile, registry.initials)
    suffix = rng.choice([s for s in tables.club_suffixes if s not in registry.suffixes])
    name = f"{city.name} {suffix}"
    code = short_code_for(city.name, registry.codes)
    nickname = rng.choice([n for n in archetype.nicknames if n not in registry.nicknames])
    colours, palette_index = pick_colours(rng.fork("colours"), tables, registry)
    registry.cities.add(city.id)
    registry.initials.add(plain(city.name)[:1])
    registry.suffixes.add(suffix)
    registry.codes.add(code)
    registry.nicknames.add(nickname)
    registry.palettes.add(palette_index)
    registry.home_primaries.add(colours.primary)
    symbol = rng.choice(tables.crest_symbols)
    return ClubIdentity(
        name=name,
        short_name=city.name,
        short_code=code,
        nickname=nickname,
        colours=colours,
        crest_description=f"a {symbol} beneath {rng.choice(tables.crest_decorations)}",
        founded_year=rng.randint(*archetype.founded),
        location=ClubLocation(
            city=city.name, region=city.region, nation_id=city.nation_id, population=city.population
        ),
        city=city,
    )
