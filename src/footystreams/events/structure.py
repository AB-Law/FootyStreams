"""Structural match events."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION
from footystreams.events.base import EventBase
from footystreams.events.context import EventContext


class KickoffEvent(EventBase):
    """Match start / period kickoff."""

    type: Literal["kickoff"] = "kickoff"
    ctx: EventContext = Field(default_factory=EventContext)
    schema_version: str = SCHEMA_VERSION
    sim_version: str = SIM_VERSION
    period: int = Field(ge=1, le=4, default=1)


class FrameEvent(EventBase):
    """Optional 1 Hz frame (must not change other events when toggled)."""

    type: Literal["frame"] = "frame"
    ctx: EventContext = Field(default_factory=EventContext)
    ball_pos_x: float = Field(ge=0.0, le=1.0)
    ball_pos_y: float = Field(ge=0.0, le=1.0)


class AddedTimeEvent(EventBase):
    """Board shows added time."""

    type: Literal["added_time"] = "added_time"
    ctx: EventContext = Field(default_factory=EventContext)
    minutes: int = Field(ge=0)


class HalftimeEvent(EventBase):
    """End of first half."""

    type: Literal["halftime"] = "halftime"
    ctx: EventContext = Field(default_factory=EventContext)
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)


class FulltimeEvent(EventBase):
    """End of match (before match_summary)."""

    type: Literal["fulltime"] = "fulltime"
    ctx: EventContext = Field(default_factory=EventContext)
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)
