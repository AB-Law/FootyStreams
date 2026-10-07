"""Schema-reserved event types unused by the v1 sim."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase
from footystreams.events.context import EventContext


class ShootoutKickEvent(EventBase):
    """Penalty shootout kick (reserved)."""

    type: Literal["shootout_kick"] = "shootout_kick"
    ctx: EventContext = Field(default_factory=EventContext)
    taker_id: PlayerId
    outcome: Literal["goal", "saved", "missed"] = "goal"


class ExtraTimeStartEvent(EventBase):
    """Extra-time start (reserved)."""

    type: Literal["extra_time_start"] = "extra_time_start"
    ctx: EventContext = Field(default_factory=EventContext)
    period: int = Field(ge=3, le=4)


class WeatherChangeEvent(EventBase):
    """Mid-match weather change (reserved)."""

    type: Literal["weather_change"] = "weather_change"
    ctx: EventContext = Field(default_factory=EventContext)
    condition: str


class CrowdReactionEvent(EventBase):
    """Crowd reaction (reserved)."""

    type: Literal["crowd_reaction"] = "crowd_reaction"
    ctx: EventContext = Field(default_factory=EventContext)
    kind: str = "cheer"


class ManagerReactionEvent(EventBase):
    """Manager reaction (reserved)."""

    type: Literal["manager_reaction"] = "manager_reaction"
    ctx: EventContext = Field(default_factory=EventContext)
    kind: str = "gesture"


class VarCheckStartedEvent(EventBase):
    """VAR check started (reserved)."""

    type: Literal["var_check_started"] = "var_check_started"
    ctx: EventContext = Field(default_factory=EventContext)
    subject_event_id: str
