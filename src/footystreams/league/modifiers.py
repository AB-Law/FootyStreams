"""Build ``StateModifier`` rows from a kind, an owner and a date (the one place they are made)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.ids import derive_id
from footystreams.domain.mood import (
    DecayKind,
    ModifierSource,
    ModifierVisibility,
    StateKind,
    StateModifier,
)
from footystreams.domain.types import EntityKind, EntityRef, Id
from footystreams.league.mood_config import MoodConfig


@dataclass(frozen=True, slots=True)
class ModifierSpec:
    """What to create: the kind, whose it is, how strong, why, and optionally how long."""

    kind: StateKind
    owner: str
    magnitude: float
    source: ModifierSource
    days: int | None = None


def new_modifier(spec: ModifierSpec, today: dt.date, config: MoodConfig) -> StateModifier:
    """A player's modifier starting ``today``; length, decay and visibility come from the kind.

    The id depends on the owner, kind, date and cause, so re-running the stage that creates it
    gives the same row.
    """
    kind, owner, source = spec.kind, spec.owner, spec.source
    effect = config.kinds[kind.value]
    cause = source.match_id or source.world_event_id or source.origin
    return StateModifier(
        id=Id(derive_id("modifier", owner, kind.value, today.isoformat(), cause)),
        owner=EntityRef(kind=EntityKind.PLAYER, id=Id(owner)),
        kind=kind,
        magnitude=round(spec.magnitude, 4),
        start_on=today,
        expires_on=today + dt.timedelta(days=spec.days or effect.default_days),
        decay=DecayKind(effect.decay),
        half_life_days=effect.half_life_days,
        source=source,
        visibility=ModifierVisibility.PUBLIC if effect.public else ModifierVisibility.PRIVATE,
        summary_key=kind.value,
    )
