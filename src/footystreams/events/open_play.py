"""Open-play action events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import UsageTag
from footystreams.domain.types import PlayerId, Pos, Signed, Unit
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
        end_pos="S",
        progressive="S",
        xt_gain="S",
    )

    type: Literal["pass"] = "pass"
    ctx: EventContext = Field(default_factory=EventContext)
    from_player_id: PlayerId
    to_player_id: PlayerId | None = None
    outcome: Literal["complete", "incomplete", "intercepted", "out"] = "complete"
    length_m: float = Field(ge=0.0, default=0.0)
    key_pass: bool = False
    end_pos: Pos | None = None  # where the ball was played to (absolute); None when not recorded
    progressive: bool = False  # moved the ball at least a quarter of the pitch toward goal
    xt_gain: float = 0.0  # threat gained (negative when played backwards)


class DribbleEvent(EventBase):
    """A take-on / carry."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(
        ctx="S",
        player_id="S",
        outcome="S",
        end_pos="S",
    )

    type: Literal["dribble"] = "dribble"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    outcome: Literal["success", "tackled", "lost"] = "success"
    end_pos: Pos | None = None


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
        big_chance="S",
        target="S",
        curve="S",
        speed_mps="S",
        loft="S",
    )

    type: Literal["shot"] = "shot"
    ctx: EventContext = Field(default_factory=EventContext)
    player_id: PlayerId
    xg: Unit = 0.0
    outcome: Literal["goal", "saved", "blocked", "off_target", "woodwork"] = "off_target"
    assist_id: PlayerId | None = None
    big_chance: bool = False  # xG at or above 0.3
    # How the shot travels (presentation only; the outcome is already decided). Absent with the
    # context off, and in logs written before schema 0.4.0.
    target: Pos | None = None  # where the ball ends up (absolute)
    curve: Signed = 0.0  # bend of the path in -1..1; the sign is the side it bows toward
    speed_mps: float = Field(ge=0.0, default=0.0)
    loft: Unit = 0.0  # peak height of the flight, 0 flat to 1 high


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
