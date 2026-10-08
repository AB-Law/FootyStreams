"""Row models inside the match summary: injuries, timelines, key moments, hooks and the maps.

Everything here is derived from the event log (the injury diagnosis aside) so `verify` and
`analytics` can recompute it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.injury import InjurySeverity
from footystreams.domain.types import PlayerId, Signed, Unit

Team = Literal["home", "away"]


class InjuryReport(DomainModel):
    """The true diagnosis of an in-match injury (the event shows only what a viewer could see)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "player_id": "L",
        "type": "L",
        "body_part": "L",
        "severity": "L",
        "expected_return_days": "L",
    }

    player_id: PlayerId
    type: str
    body_part: str
    severity: InjurySeverity
    expected_return_days: int = Field(ge=0, default=0)


class MomentumPoint(DomainModel):
    """Momentum (home-positive) at a second of match time."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"t": "L", "momentum": "L"}

    t: int = Field(ge=0)
    momentum: Signed = 0.0


class XgPoint(DomainModel):
    """Cumulative xG of both sides at a second of match time."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"t": "L", "home": "L", "away": "L"}

    t: int = Field(ge=0)
    home: float = Field(ge=0.0)
    away: float = Field(ge=0.0)


class KeyMoment(DomainModel):
    """An event worth replaying: it cleared the significance threshold."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "event_id": "L",
        "kind": "L",
        "significance": "L",
        "t": "L",
    }

    event_id: str
    kind: str
    significance: Unit
    t: int = Field(ge=0)


class Hook(DomainModel):
    """A deterministic story seed for the narrator and memory layers (a key, not prose)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "L",
        "event_ids": "L",
        "magnitude": "L",
        "text_key": "L",
    }

    kind: str
    event_ids: tuple[str, ...] = ()
    magnitude: float = Field(ge=0.0, default=0.0)
    text_key: str = ""


class PassLink(DomainModel):
    """Completed passes from one player to another."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "passer_id": "L",
        "receiver_id": "L",
        "count": "L",
    }

    passer_id: PlayerId
    receiver_id: PlayerId
    count: int = Field(ge=1)


class ZoneFlow(DomainModel):
    """Completed passes between two zones of a 12 x 8 grid, in the passing team's frame."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "team": "L",
        "from_zone": "L",
        "to_zone": "L",
        "count": "L",
    }

    team: Team
    from_zone: int = Field(ge=0, lt=96)
    to_zone: int = Field(ge=0, lt=96)
    count: int = Field(ge=1)


class ShotPoint(DomainModel):
    """One shot on the shot map."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "event_id": "L",
        "team": "L",
        "x": "L",
        "y": "L",
        "xg": "L",
        "outcome": "L",
    }

    event_id: str
    team: Team
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    xg: Unit
    outcome: str
