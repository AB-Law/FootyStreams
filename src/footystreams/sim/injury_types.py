"""The injuries a match can produce: what they are, how severe, how likely among their cause.

A built-in table rather than a data file (the sim reads no files); weights are relative within a
cause. `base_days` is the typical layoff, kept for the league layer through the match summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from footystreams.domain.injury import InjurySeverity

InjuryCause = Literal["contact", "non_contact", "foul"]


@dataclass(frozen=True, slots=True)
class InjuryType:
    """One kind of injury with its severity and relative frequency."""

    name: str
    body_part: str
    severity: InjurySeverity
    weight: float
    base_days: int


_KNOCK, _MINOR = InjurySeverity.KNOCK, InjurySeverity.MINOR
_MODERATE, _SEVERE = InjurySeverity.MODERATE, InjurySeverity.SEVERE

CONTACT_TYPES = (
    InjuryType("bruised thigh", "thigh", _KNOCK, 0.30, 0),
    InjuryType("knock to the ankle", "ankle", _KNOCK, 0.20, 0),
    InjuryType("knock to the head", "head", _KNOCK, 0.12, 2),
    InjuryType("ankle sprain", "ankle", _MINOR, 0.14, 10),
    InjuryType("dead leg", "thigh", _MINOR, 0.08, 7),
    InjuryType("knee sprain", "knee", _MODERATE, 0.10, 28),
    InjuryType("broken foot", "foot", _MODERATE, 0.03, 56),
    InjuryType("knee ligament rupture", "knee", _SEVERE, 0.03, 220),
)

NON_CONTACT_TYPES = (
    InjuryType("cramp", "calf", _KNOCK, 0.20, 0),
    InjuryType("hamstring strain", "hamstring", _MINOR, 0.28, 14),
    InjuryType("calf strain", "calf", _MINOR, 0.18, 10),
    InjuryType("groin strain", "groin", _MODERATE, 0.14, 21),
    InjuryType("hamstring tear", "hamstring", _MODERATE, 0.14, 35),
    InjuryType("achilles rupture", "achilles", _SEVERE, 0.06, 240),
)


def types_for(cause: InjuryCause) -> tuple[InjuryType, ...]:
    """Return the injury types a cause can produce (a foul is contact)."""
    return NON_CONTACT_TYPES if cause == "non_contact" else CONTACT_TYPES
