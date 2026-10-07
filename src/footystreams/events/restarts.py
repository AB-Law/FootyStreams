"""Restart events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import UsageTag
from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase, event_usage
from footystreams.events.context import EventContext


class ThrowInEvent(EventBase):
    """Throw-in."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", taker_id="S")

    type: Literal["throw_in"] = "throw_in"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId


class GoalKickEvent(EventBase):
    """Goal kick."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", taker_id="S")

    type: Literal["goal_kick"] = "goal_kick"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId


class CornerEvent(EventBase):
    """Corner kick."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        taker_id="S",
        side="S",
    )

    type: Literal["corner"] = "corner"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    side: Literal["left", "right"] = "left"


class FreeKickEvent(EventBase):
    """Free kick."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        taker_id="S",
        kind="S",
    )

    type: Literal["free_kick"] = "free_kick"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    kind: Literal["direct", "indirect"] = "direct"


class PenaltyEvent(EventBase):
    """Penalty kick."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        taker_id="S",
        outcome="S",
    )

    type: Literal["penalty"] = "penalty"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    outcome: Literal["goal", "saved", "missed", "woodwork"] = "goal"
