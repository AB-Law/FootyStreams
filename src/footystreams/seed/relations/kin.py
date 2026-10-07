"""Family ties: two Valmerian players at one club who share a surname."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind
from footystreams.seed.names.book import NameBook
from footystreams.seed.relations.builder import RelationshipBuilder

MIN_AGE_GAP_FOR_PARENT = 18
KIN_STRENGTH = (0.7, 1.0)


@dataclass(frozen=True, slots=True)
class KinPair:
    """The elder, and the relative who has taken the elder's surname."""

    elder: Player
    relative: Player


def _short_surname(player: Player) -> str:
    return player.last_name.split(" ")[-1]


def make_kin(
    rng: WorldRng,
    builder: RelationshipBuilder,
    candidates: Sequence[Player],
    names: NameBook,
) -> KinPair | None:
    """Pair two candidates (same nationality), give the younger the elder's surname.

    Returns None when no two candidates share a nationality or the shared known_as is taken.
    """
    ordered = sorted(candidates, key=lambda p: (p.date_of_birth, p.id))
    for elder in rng.shuffled(ordered):
        younger = [
            p
            for p in ordered
            if p.id != elder.id
            and p.nationality == elder.nationality
            and p.date_of_birth > elder.date_of_birth
        ]
        if not younger:
            continue
        relative = rng.choice(younger)
        known_as = f"{relative.first_name} {_short_surname(elder)}"
        if not names.claim(known_as):
            continue
        renamed = relative.model_copy(
            update={
                "last_name": elder.last_name,
                "known_as": known_as,
                "pronunciation": elder.pronunciation,
            }
        )
        kind = "family"
        builder.add(
            kind,
            builder.ref(EntityKind.PLAYER, elder.id),
            builder.ref(EntityKind.PLAYER, renamed.id),
            rng.uniform(*KIN_STRENGTH),
            valence=rng.uniform(0.5, 1.0),
        )
        return KinPair(elder, renamed)
    return None
