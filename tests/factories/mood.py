"""Builders for state modifiers."""

from __future__ import annotations

import datetime as dt
from typing import Any

from footystreams.domain.mood import (
    DecayKind,
    ModifierSource,
    ModifierVisibility,
    StateKind,
    StateModifier,
)
from footystreams.domain.types import EntityKind, EntityRef, Id

TODAY = dt.date(2031, 8, 1)


def make_modifier(**overrides: Any) -> StateModifier:
    """A full-strength public ``personal_turmoil`` starting today, lasting 20 days."""
    values: dict[str, Any] = {
        "id": Id("mod_00001"),
        "owner": EntityRef(kind=EntityKind.PLAYER, id=Id("plr_00001")),
        "kind": StateKind.PERSONAL_TURMOIL,
        "magnitude": 1.0,
        "start_on": TODAY,
        "expires_on": TODAY + dt.timedelta(days=20),
        "decay": DecayKind.LINEAR,
        "source": ModifierSource(origin="rule"),
        "visibility": ModifierVisibility.PUBLIC,
        "summary_key": "difficult_week",
    }
    values.update(overrides)
    return StateModifier(**values)
