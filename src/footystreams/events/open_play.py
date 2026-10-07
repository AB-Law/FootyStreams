"""Open-play action events."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from footystreams.domain.types import PlayerId, Unit
from footystreams.events.base import EventBase
from footystreams.events.context import EventContext


class PassEvent(EventBase):
    """A pass attempt."""

    type: Literal["pass"] = "pass"
    ctx: EventContext = Field(default_factory=EventContext)
    from_player_id: PlayerId
    to_player_id: PlayerId | None = None
    outcome: Literal["complete", "incomplete", "intercepted", "out"] = "complete"
    length_m: float = Field(ge=0.0, default=0.0)
    key_pass: bool = False


class DribbleEvent(EventBase):
    """A take-on / carry."""

    type: Literal["dribble"] = "dribble"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    outcome: Literal["success", "tackled", "lost"] = "success"


class TackleEvent(EventBase):
    """A tackle attempt."""

    type: Literal["tackle"] = "tackle"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    target_id: PlayerId
    outcome: Literal["won", "foul", "missed"] = "won"


class InterceptionEvent(EventBase):
    """An interception."""

    type: Literal["interception"] = "interception"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId


class ClearanceEvent(EventBase):
    """A clearance."""

    type: Literal["clearance"] = "clearance"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId


class ShotEvent(EventBase):
    """A shot attempt."""

    type: Literal["shot"] = "shot"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    xg: Unit = 0.0
    outcome: Literal["goal", "saved", "blocked", "off_target", "woodwork"] = "off_target"
    assist_id: PlayerId | None = None


class SaveEvent(EventBase):
    """A goalkeeper save."""

    type: Literal["save"] = "save"
    ctx: EventContext = Field(default_factory=EventContext)
    keeper_id: PlayerId
    shot_event_id: str


class GoalEvent(EventBase):
    """A confirmed goal."""

    type: Literal["goal"] = "goal"
    ctx: EventContext = Field(default_factory=EventContext)
    scorer_id: PlayerId
    assist_id: PlayerId | None = None
    shot_event_id: str | None = None
    own_goal: bool = False


class OffsideEvent(EventBase):
    """An offside offence."""

    type: Literal["offside"] = "offside"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
