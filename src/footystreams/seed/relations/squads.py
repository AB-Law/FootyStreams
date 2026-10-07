"""Relationships inside and around a club: friendships, mentors, rivals and manager trust."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind, Position
from footystreams.seed.clubs.generator import ClubDraft
from footystreams.seed.relations.builder import RelationshipBuilder

CLUSTERS_PER_CLUB = (2, 4)
CLUSTER_SIZE = (3, 5)
FRIEND_STRENGTH = (0.4, 0.9)
FRIEND_VALENCE = (0.2, 0.9)
MENTOR_PAIRS = 2
MENTOR_MIN_AGE = 30
MENTOR_STRENGTH = (0.5, 0.9)
RIVAL_PAIRS = (0, 2)
RIVAL_STRENGTH = (0.3, 0.7)
RIVAL_VALENCE = (-0.7, -0.2)
TRUST_PLAYERS = 6
TRUST_STRENGTH = (0.4, 0.9)
TRUST_VALENCE = (0.1, 0.9)
BOARD_TRUST = (0.4, 0.9)
BOARD_VALENCE = (-0.2, 0.8)
NEAR_AGE_GAP = 3
NATIONALITY_WEIGHT = 2.0
LINES: dict[Position, int] = {
    Position.GK: 0, Position.CB: 1, Position.RB: 1, Position.LB: 1, Position.RWB: 1,
    Position.LWB: 1, Position.DM: 2, Position.CM: 2, Position.AM: 2, Position.RM: 2,
    Position.LM: 2, Position.RW: 3, Position.LW: 3, Position.SS: 3, Position.ST: 3,
}  # fmt: skip


def _affinity(rng: WorldRng, seed: Player, other: Player, today: dt.date) -> float:
    """How likely two players are to befriend: shared nationality, similar age, same line."""
    score = NATIONALITY_WEIGHT if seed.nationality == other.nationality else 0.0
    if abs(seed.age_on(today) - other.age_on(today)) <= NEAR_AGE_GAP:
        score += 1.0
    if LINES[seed.primary_position] == LINES[other.primary_position]:
        score += 1.0
    return score + rng.u()


def friendships(
    rng: WorldRng, builder: RelationshipBuilder, seniors: Sequence[Player], today: dt.date
) -> None:
    """2-4 friendship clusters per club, each fully connected."""
    for cluster in range(rng.randint(*CLUSTERS_PER_CLUB)):
        stream = rng.fork(f"cluster:{cluster}")
        seed = stream.choice(seniors)
        ranked = sorted(
            (p for p in seniors if p.id != seed.id),
            key=lambda p: -_affinity(stream, seed, p, today),
        )
        members = [seed, *ranked[: stream.randint(*CLUSTER_SIZE) - 1]]
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                builder.add(
                    "friend",
                    builder.ref(EntityKind.PLAYER, left.id),
                    builder.ref(EntityKind.PLAYER, right.id),
                    stream.uniform(*FRIEND_STRENGTH),
                    valence=stream.uniform(*FRIEND_VALENCE),
                )


def mentors(
    rng: WorldRng,
    builder: RelationshipBuilder,
    pool: tuple[Sequence[Player], Sequence[Player]],
    today: dt.date,
) -> None:
    """The most senior leaders mentor youth prospects: the veteran is `a`, the prospect `b`."""
    seniors, youth = pool
    veterans = sorted(
        (p for p in seniors if p.age_on(today) >= MENTOR_MIN_AGE),
        key=lambda p: (-p.mental.leadership, p.id),
    )[:MENTOR_PAIRS]
    for veteran, prospect in zip(veterans, rng.shuffled(list(youth)), strict=False):
        builder.add(
            "mentor_of",
            builder.ref(EntityKind.PLAYER, veteran.id),
            builder.ref(EntityKind.PLAYER, prospect.id),
            rng.uniform(*MENTOR_STRENGTH),
            valence=rng.uniform(*FRIEND_VALENCE),
        )


def rivals(rng: WorldRng, builder: RelationshipBuilder, players: Sequence[Player]) -> None:
    """0-2 rival pairs from the same position line (youth-academy grudges)."""
    for _ in range(rng.randint(*RIVAL_PAIRS)):
        first = rng.choice(players)
        line = LINES[first.primary_position]
        candidates = [p for p in players if p.id != first.id and LINES[p.primary_position] == line]
        if candidates:
            builder.add(
                "rival",
                builder.ref(EntityKind.PLAYER, first.id),
                builder.ref(EntityKind.PLAYER, rng.choice(candidates).id),
                rng.uniform(*RIVAL_STRENGTH),
                valence=rng.uniform(*RIVAL_VALENCE),
            )


def manager_ties(
    rng: WorldRng, builder: RelationshipBuilder, draft: ClubDraft, seniors: Sequence[Player]
) -> None:
    """Manager trust in his best players and in his board."""
    manager = builder.ref(EntityKind.MANAGER, draft.manager.id)
    for player in sorted(seniors, key=lambda p: (-p.ability_current, p.id))[:TRUST_PLAYERS]:
        builder.add(
            "trust",
            manager,
            builder.ref(EntityKind.PLAYER, player.id),
            rng.uniform(*TRUST_STRENGTH),
            valence=rng.uniform(*TRUST_VALENCE),
        )
    builder.add(
        "trust",
        manager,
        builder.ref(EntityKind.CLUB, draft.club.id),
        rng.uniform(*BOARD_TRUST),
        valence=rng.uniform(*BOARD_VALENCE),
    )
