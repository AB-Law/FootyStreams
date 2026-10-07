"""Structural match events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import UsageTag
from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION
from footystreams.events.base import EventBase, event_usage
from footystreams.events.context import EventContext


class KickoffEvent(EventBase):
    """Match start / period kickoff."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        schema_version="S",
        sim_version="S",
        period="S",
    )

    type: Literal["kickoff"] = "kickoff"
    ctx: EventContext = Field(default_factory=EventContext)
    schema_version: str = SCHEMA_VERSION
    sim_version: str = SIM_VERSION
    period: int = Field(ge=1, le=4, default=1)


class FrameEvent(EventBase):
    """Optional 1 Hz frame (must not change other events when toggled)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        ball_pos_x="S",
        ball_pos_y="S",
    )

    type: Literal["frame"] = "frame"
    ctx: EventContext = Field(default_factory=EventContext)
    ball_pos_x: float = Field(ge=0.0, le=1.0)
    ball_pos_y: float = Field(ge=0.0, le=1.0)


class AddedTimeEvent(EventBase):
    """Board shows added time."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", minutes="S")

    type: Literal["added_time"] = "added_time"
    ctx: EventContext = Field(default_factory=EventContext)
    minutes: int = Field(ge=0)


class HalftimeEvent(EventBase):
    """End of first half."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        score_home="S",
        score_away="S",
    )

    type: Literal["halftime"] = "halftime"
    ctx: EventContext = Field(default_factory=EventContext)
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)


class FulltimeEvent(EventBase):
    """End of match (before match_summary)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        score_home="S",
        score_away="S",
    )

    type: Literal["fulltime"] = "fulltime"
    ctx: EventContext = Field(default_factory=EventContext)
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)
