"""Relationships of the broadcast crew: duos, a feud, a mentor, club affinities and favourites."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.club import Club
from footystreams.domain.media import MediaPersonality
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind
from footystreams.seed.relations.builder import RelationshipBuilder

# (kind, archetype a, archetype b, strength, valence)
CREW_TIES: tuple[tuple[str, str, str, float, float], ...] = (
    ("colleague", "old_hand", "tactician", 0.90, 0.8),
    ("colleague", "firecracker", "stats_nerd", 0.85, 0.7),
    ("feud", "cynic_pundit", "optimist_pundit", 0.80, -0.5),
    ("mentor_of", "polished_anchor", "warm_presenter", 0.70, 0.6),
)
LOCAL_HERO = "local_hero"
ADORED_STRENGTH, DISLIKED_STRENGTH = 0.95, 0.60
FAVOURITE_STRENGTH, DISLIKE_STRENGTH = (0.5, 0.9), (0.4, 0.8)


def crew_ties(builder: RelationshipBuilder, crew: Mapping[str, MediaPersonality]) -> None:
    """The scripted pairings between crew members (by authored persona key)."""
    for kind, left, right, strength, valence in CREW_TIES:
        builder.add(
            kind,
            builder.ref(EntityKind.MEDIA, crew[left].id),
            builder.ref(EntityKind.MEDIA, crew[right].id),
            strength,
            valence=valence,
        )


def club_affinities(
    rng: WorldRng,
    builder: RelationshipBuilder,
    crew: Mapping[str, MediaPersonality],
    clubs: Sequence[Club],
) -> None:
    """The Local Hero adores one club and quietly dislikes another."""
    adored, disliked = rng.shuffled(list(clubs))[:2]
    hero = builder.ref(EntityKind.MEDIA, crew[LOCAL_HERO].id)
    builder.add(
        "admires", hero, builder.ref(EntityKind.CLUB, adored.id), ADORED_STRENGTH, valence=0.9
    )
    builder.add(
        "dislikes", hero, builder.ref(EntityKind.CLUB, disliked.id), DISLIKED_STRENGTH, valence=-0.6
    )


def favourite_players(
    rng: WorldRng,
    builder: RelationshipBuilder,
    crew: Sequence[MediaPersonality],
    players: Sequence[Player],
) -> None:
    """Every crew member has one favourite and one disliked player."""
    for member in crew:
        stream = rng.fork(member.id)
        favourite, disliked = stream.shuffled(list(players))[:2]
        person = builder.ref(EntityKind.MEDIA, member.id)
        builder.add(
            "admires",
            person,
            builder.ref(EntityKind.PLAYER, favourite.id),
            stream.uniform(*FAVOURITE_STRENGTH),
            valence=0.6,
        )
        builder.add(
            "dislikes",
            person,
            builder.ref(EntityKind.PLAYER, disliked.id),
            stream.uniform(*DISLIKE_STRENGTH),
            valence=-0.5,
        )
