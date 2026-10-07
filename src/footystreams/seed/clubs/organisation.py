"""Board, facilities, academy and culture of a club."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.club import Board, ClubCulture, Facilities, YouthAcademy
from footystreams.domain.manager import Objective
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import PlayerId
from footystreams.seed.clubs.archetypes import ClubArchetype

CULTURE_KEYS = (
    "youth_focus", "spending_pride", "tactical_identity", "discipline",
    "media_openness", "loyalty_to_manager", "glamour", "grit",
)  # fmt: skip
CULTURE_BASELINE = (0.2, 0.7)
CULTURE_EMPHASIS = (0.78, 0.95)
TAG_TO_CULTURE_KEY = {
    "youth_focus": "youth_focus",
    "glamour": "glamour",
    "tactical": "tactical_identity",
    "discipline": "discipline",
    "grit": "grit",
    "loyalty": "loyalty_to_manager",
    "tradition": "loyalty_to_manager",
    "expectations": "spending_pride",
    "debt": "spending_pride",
}
MANAGER_CONFIDENCE_RANGE = (0.5, 0.75)
INTAKE_QUALITY_FLOOR = 0.3
PERCENT = 100.0


def make_board(rng: WorldRng, archetype: ClubArchetype, deadline: dt.date) -> Board:
    """Board dispositions from the archetype, with the first season's headline objective."""
    spec = archetype.board
    return Board(
        ambition=rng.randint(*spec.ambition),
        patience=rng.randint(*spec.patience),
        meddling=rng.randint(*spec.meddling),
        budget_strictness=rng.randint(*spec.budget_strictness),
        expectations=(
            Objective(kind=spec.objective.kind, target=spec.objective.target, deadline=deadline),
        ),
        manager_confidence=rng.uniform(*MANAGER_CONFIDENCE_RANGE),
    )


def make_facilities(rng: WorldRng, archetype: ClubArchetype) -> Facilities:
    """Facility levels from the archetype's ranges."""
    spec = archetype.facilities
    return Facilities(
        training=rng.randint(*spec.training),
        youth=rng.randint(*spec.youth),
        medical=rng.randint(*spec.medical),
    )


def make_academy(
    rng: WorldRng, archetype: ClubArchetype, prospects: tuple[PlayerId, ...]
) -> YouthAcademy:
    """Academy whose intake size and quality follow the youth facility level."""
    spec = archetype.facilities
    level = rng.randint(*spec.youth)
    return YouthAcademy(
        level=level,
        intake_size=rng.randint(*spec.intake),
        intake_quality=max(INTAKE_QUALITY_FLOOR, level / PERCENT),
        philosophy_tag="develop_and_sell" if archetype.young_squad else "balanced_intake",
        prospect_ids=prospects,
    )


def make_culture(rng: WorldRng, archetype: ClubArchetype) -> ClubCulture:
    """Soft cultural values; tags push the matching keys high."""
    values = {key: rng.uniform(*CULTURE_BASELINE) for key in CULTURE_KEYS}
    for tag in archetype.culture_tags:
        key = TAG_TO_CULTURE_KEY.get(tag)
        if key is not None:
            values[key] = rng.uniform(*CULTURE_EMPHASIS)
    return ClubCulture(values=values, tags=archetype.culture_tags)
