"""Discriminated MatchEvent union."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, TypeAdapter

from footystreams.events.discipline import (
    CardEvent,
    FoulEvent,
    InjuryEvent,
    ReviewEvent,
    SubstitutionEvent,
    TacticalChangeEvent,
)
from footystreams.events.open_play import (
    ClearanceEvent,
    DribbleEvent,
    GoalEvent,
    InterceptionEvent,
    OffsideEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.reserved import (
    CrowdReactionEvent,
    ExtraTimeStartEvent,
    ManagerReactionEvent,
    ShootoutKickEvent,
    VarCheckStartedEvent,
    WeatherChangeEvent,
)
from footystreams.events.restarts import (
    CornerEvent,
    FreeKickEvent,
    GoalKickEvent,
    PenaltyEvent,
    ThrowInEvent,
)
from footystreams.events.structure import (
    AddedTimeEvent,
    FrameEvent,
    FulltimeEvent,
    HalftimeEvent,
    KickoffEvent,
)
from footystreams.events.summary import MatchSummaryEvent

EVENT_CLASSES = (
    KickoffEvent,
    FrameEvent,
    AddedTimeEvent,
    HalftimeEvent,
    FulltimeEvent,
    MatchSummaryEvent,
    PassEvent,
    DribbleEvent,
    TackleEvent,
    InterceptionEvent,
    ClearanceEvent,
    ShotEvent,
    SaveEvent,
    GoalEvent,
    OffsideEvent,
    FoulEvent,
    CardEvent,
    InjuryEvent,
    SubstitutionEvent,
    TacticalChangeEvent,
    ReviewEvent,
    ThrowInEvent,
    GoalKickEvent,
    CornerEvent,
    FreeKickEvent,
    PenaltyEvent,
    ShootoutKickEvent,
    ExtraTimeStartEvent,
    WeatherChangeEvent,
    CrowdReactionEvent,
    ManagerReactionEvent,
    VarCheckStartedEvent,
)

MatchEvent = Annotated[
    KickoffEvent
    | FrameEvent
    | AddedTimeEvent
    | HalftimeEvent
    | FulltimeEvent
    | MatchSummaryEvent
    | PassEvent
    | DribbleEvent
    | TackleEvent
    | InterceptionEvent
    | ClearanceEvent
    | ShotEvent
    | SaveEvent
    | GoalEvent
    | OffsideEvent
    | FoulEvent
    | CardEvent
    | InjuryEvent
    | SubstitutionEvent
    | TacticalChangeEvent
    | ReviewEvent
    | ThrowInEvent
    | GoalKickEvent
    | CornerEvent
    | FreeKickEvent
    | PenaltyEvent
    | ShootoutKickEvent
    | ExtraTimeStartEvent
    | WeatherChangeEvent
    | CrowdReactionEvent
    | ManagerReactionEvent
    | VarCheckStartedEvent,
    Field(discriminator="type"),
]

MATCH_EVENT_ADAPTER: TypeAdapter[MatchEvent] = TypeAdapter(MatchEvent)

EVENT_TYPE_NAMES: tuple[str, ...] = tuple(
    str(cls.model_fields["type"].default) for cls in EVENT_CLASSES
)
