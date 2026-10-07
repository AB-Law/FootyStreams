"""Discipline and substitution events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase, event_usage
from footystreams.events.context import EventContext


class TacticsChange(DomainModel):
    """One module-path change on a tactical_change event."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"field": "S", "value": "S"}

    field: str
    value: str


class FoulEvent(EventBase):
    """A foul."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        fouler_id="S",
        fouled_id="S",
        severity="S",
    )

    type: Literal["foul"] = "foul"
    ctx: EventContext = Field(default_factory=EventContext)
    fouler_id: PlayerId
    fouled_id: PlayerId
    severity: Literal["careless", "reckless", "violent"] = "careless"


class CardEvent(EventBase):
    """A yellow or red card."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_id="S",
        colour="S",
        reason="S",
    )

    type: Literal["card"] = "card"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    colour: Literal["yellow", "red", "second_yellow"]
    reason: str = ""


class InjuryEvent(EventBase):
    """An in-match injury stoppage (apparent only)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_id="S",
        cause="S",
        body_part="S",
        apparent_severity="S",
        can_continue="S",
        stoppage_s="S",
        caused_by_player_id="S",
    )

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

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_off_id="S",
        player_on_id="S",
        reason="S",
    )

    type: Literal["substitution"] = "substitution"
    ctx: EventContext = Field(default_factory=EventContext)
    player_off_id: PlayerId
    player_on_id: PlayerId
    reason: str = "tactical"


class TacticalChangeEvent(EventBase):
    """In-match tactics patch."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", changes="S")

    type: Literal["tactical_change"] = "tactical_change"
    ctx: EventContext = Field(default_factory=EventContext)
    changes: tuple[TacticsChange, ...] = ()


class ReviewEvent(EventBase):
    """Video review outcome."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        subject_event_id="S",
        outcome="S",
    )

    type: Literal["review"] = "review"
    ctx: EventContext = Field(default_factory=EventContext)
    subject_event_id: str
    outcome: Literal["confirmed", "overturned", "inconclusive"] = "confirmed"
