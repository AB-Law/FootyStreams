"""Plan the league's shape: which archetype each club gets and how strong it is."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.rng import WorldRng
from footystreams.seed.clubs.archetypes import ClubTables

QUALITY_SAMPLE_BAND = (0.2, 0.8)  # stay off the band edges so neighbours can be spaced apart
MIN_SPACING = 1.5  # target team ratings of neighbouring clubs differ by at least this


@dataclass(frozen=True, slots=True)
class ClubSlot:
    """One club's place in the league: its archetype and target team rating."""

    archetype_key: str
    quality: float


def plan_league(rng: WorldRng, tables: ClubTables, clubs: int) -> tuple[ClubSlot, ...]:
    """Pick ``clubs`` archetypes (shuffled by the seed) and spaced-out target strengths.

    The returned order is the order clubs are generated in, so ids depend on the shuffle.
    """
    keys = rng.fork("archetypes").shuffled(sorted(tables.archetypes))[:clubs]
    quality_rng = rng.fork("quality")
    drawn = {
        key: quality_rng.uniform(
            tables.archetypes[key].quality[0]
            + (tables.archetypes[key].quality[1] - tables.archetypes[key].quality[0])
            * QUALITY_SAMPLE_BAND[0],
            tables.archetypes[key].quality[0]
            + (tables.archetypes[key].quality[1] - tables.archetypes[key].quality[0])
            * QUALITY_SAMPLE_BAND[1],
        )
        for key in keys
    }
    spaced: dict[str, float] = {}
    previous = float("-inf")
    for key in sorted(drawn, key=lambda item: (drawn[item], item)):
        previous = max(drawn[key], previous + MIN_SPACING)
        spaced[key] = previous
    return tuple(ClubSlot(key, round(spaced[key], 2)) for key in keys)
