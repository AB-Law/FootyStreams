"""Discipline and substitution events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase
from footystreams.events.context import EventContext


class TacticsChange(DomainModel):
    """One module-path change on a tactical_change event."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"field": "S", "value": "S"}

    field: str
    value: str


class FoulEvent(EventBase):
    """A foul."""

    type: Literal["foul"] = "foul"
    ctx: EventContext = Field(default_factory=EventContext)
    fouler_id: PlayerId
    fouled_id: PlayerId
    severity: Literal["careless", "reckless", "violent"] = "careless"


class CardEvent(EventBase):
    """A yellow or red card."""

    type: Literal["card"] = "card"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    colour: Literal["yellow", "red", "second_yellow"]
    reason: str = ""


class InjuryEvent(EventBase):
    """An in-match injury stoppage (apparent only)."""

    type: Literal["injury"] = "injury"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    cause: Literal["contact", "non_contact", "foul"] = "non_contact"
    body_part: str = "unknown"
    apparent_severity: Literal["looks_minor", "needs_treatment", "looks_serious"] = "looks_minor"
    can_continue: bool = True
    stoppage_s: int = Field(ge=0, default=0)
    caused_by_player_id: PlayerId | None = None


class SubstitutionEvent(EventBase):
    """A substitution."""

    type: Literal["substitution"] = "substitution"
    ctx: EventContext = Field(default_factory=EventContext)
    player_off_id: PlayerId
    player_on_id: PlayerId
    reason: str = "tactical"


class TacticalChangeEvent(EventBase):
    """In-match tactics patch."""

    type: Literal["tactical_change"] = "tactical_change"
    ctx: EventContext = Field(default_factory=EventContext)
    changes: tuple[TacticsChange, ...] = ()


class ReviewEvent(EventBase):
    """Video review outcome."""

    type: Literal["review"] = "review"
    ctx: EventContext = Field(default_factory=EventContext)
    subject_event_id: str
    outcome: Literal["confirmed", "overturned", "inconclusive"] = "confirmed"
