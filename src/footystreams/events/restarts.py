"""Restart events."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase
from footystreams.events.context import EventContext


class ThrowInEvent(EventBase):
    """Throw-in."""

    type: Literal["throw_in"] = "throw_in"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId


class GoalKickEvent(EventBase):
    """Goal kick."""

    type: Literal["goal_kick"] = "goal_kick"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId


class CornerEvent(EventBase):
    """Corner kick."""

    type: Literal["corner"] = "corner"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    side: Literal["left", "right"] = "left"


class FreeKickEvent(EventBase):
    """Free kick."""

    type: Literal["free_kick"] = "free_kick"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    kind: Literal["direct", "indirect"] = "direct"


class PenaltyEvent(EventBase):
    """Penalty kick."""

    type: Literal["penalty"] = "penalty"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    outcome: Literal["goal", "saved", "missed", "woodwork"] = "goal"
