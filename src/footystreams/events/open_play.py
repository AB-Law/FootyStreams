"""Open-play action events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import UsageTag
from footystreams.domain.types import PlayerId, Unit
from footystreams.events.base import EventBase, event_usage
from footystreams.events.context import EventContext


class PassEvent(EventBase):
    """A pass attempt."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        from_player_id="S",
        to_player_id="S",
        outcome="S",
        length_m="S",
        key_pass="S",  # noqa: S106 — football "key pass", not a password
    )

    type: Literal["pass"] = "pass"
    ctx: EventContext = Field(default_factory=EventContext)
    from_player_id: PlayerId
    to_player_id: PlayerId | None = None
    outcome: Literal["complete", "incomplete", "intercepted", "out"] = "complete"
    length_m: float = Field(ge=0.0, default=0.0)
    key_pass: bool = False


class DribbleEvent(EventBase):
    """A take-on / carry."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_id="S",
        outcome="S",
    )

    type: Literal["dribble"] = "dribble"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    outcome: Literal["success", "tackled", "lost"] = "success"


class TackleEvent(EventBase):
    """A tackle attempt."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_id="S",
        target_id="S",
        outcome="S",
    )

    type: Literal["tackle"] = "tackle"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    target_id: PlayerId
    outcome: Literal["won", "foul", "missed"] = "won"


class InterceptionEvent(EventBase):
    """An interception."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", player_id="S")

    type: Literal["interception"] = "interception"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId


class ClearanceEvent(EventBase):
    """A clearance."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", player_id="S")

    type: Literal["clearance"] = "clearance"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId


class ShotEvent(EventBase):
    """A shot attempt."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_id="S",
        xg="S",
        outcome="S",
        assist_id="S",
    )

    type: Literal["shot"] = "shot"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    xg: Unit = 0.0
    outcome: Literal["goal", "saved", "blocked", "off_target", "woodwork"] = "off_target"
    assist_id: PlayerId | None = None


class SaveEvent(EventBase):
    """A goalkeeper save."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        keeper_id="S",
        shot_event_id="S",
    )

    type: Literal["save"] = "save"
    ctx: EventContext = Field(default_factory=EventContext)
    keeper_id: PlayerId
    shot_event_id: str


class GoalEvent(EventBase):
    """A confirmed goal."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        scorer_id="S",
        assist_id="S",
        shot_event_id="S",
        own_goal="S",
    )

    type: Literal["goal"] = "goal"
    ctx: EventContext = Field(default_factory=EventContext)
    scorer_id: PlayerId
    assist_id: PlayerId | None = None
    shot_event_id: str | None = None
    own_goal: bool = False


class OffsideEvent(EventBase):
    """An offside offence."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", player_id="S")

    type: Literal["offside"] = "offside"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
