"""Broadcast events: everything the engine emits, match events and the programme around them.

A ``BroadcastEvent`` is a ``MatchEvent`` (replayed unchanged from the stored log) or one of three
things only the engine knows about: a programme segment starting or ending, a world notice, and an
engine marker (start, resume, stop, degraded). Every event has a stable ``id`` so a consumer can
drop a repeat: a match event keeps its ``{match_id}:{seq}`` id, and the rest are derived from the
programme block or the marker, never from the clock.

Segments carry structured facts and a placeholder duration; the commentary and studio layers fill
them later (docs/design/13 section 3).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import Field, TypeAdapter

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.events.types import MatchEvent

Fact = str | int | float | bool


class SegmentKind(StrEnum):
    """The kinds of programme block that are not a match."""

    PRE_MATCH = "pre_match"
    HALF_TIME = "half_time"
    POST_MATCH = "post_match"
    MATCHDAY_MAGAZINE = "matchday_magazine"
    FILLER = "filler"


class MarkerKind(StrEnum):
    """What an engine marker announces."""

    START = "start"
    RESUME = "resume"
    STOP = "stop"
    DEGRADED = "degraded"
    RECOVERED = "recovered"


class SegmentStartedEvent(DomainModel):
    """A programme segment begins; ``facts`` is what a presenter may talk about."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "type": "L",
        "block_id": "L",
        "kind": "L",
        "subject_ref": "L",
        "duration_s": "L",
        "facts": "L",
    }

    id: str
    type: Literal["segment_started"] = "segment_started"
    block_id: str
    kind: SegmentKind
    subject_ref: str = ""
    duration_s: float = Field(ge=0.0)
    facts: Mapping[str, Fact] = Field(default_factory=dict)


class SegmentEndedEvent(DomainModel):
    """A programme segment ends."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "type": "L",
        "block_id": "L",
        "kind": "L",
    }

    id: str
    type: Literal["segment_ended"] = "segment_ended"
    block_id: str
    kind: SegmentKind


class WorldNotice(DomainModel):
    """A fact from the world's news feed, delivered to the channel."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "type": "L",
        "world_event_id": "L",
        "notice_kind": "L",
        "facts": "L",
    }

    id: str
    type: Literal["world_notice"] = "world_notice"
    world_event_id: str
    notice_kind: str
    facts: Mapping[str, Fact] = Field(default_factory=dict)


class EngineMarker(DomainModel):
    """The engine saying something about itself; ``resume_*`` say where playback picks up."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "type": "L",
        "marker": "L",
        "detail": "L",
        "resume_match_id": "L",
        "resume_after_seq": "L",
    }

    id: str
    type: Literal["engine_marker"] = "engine_marker"
    marker: MarkerKind
    detail: str = ""
    resume_match_id: str | None = None
    resume_after_seq: int | None = Field(ge=-1, default=None)


BroadcastEvent = Annotated[
    MatchEvent | SegmentStartedEvent | SegmentEndedEvent | WorldNotice | EngineMarker,
    Field(discriminator="type"),
]

BROADCAST_EVENT_ADAPTER: TypeAdapter[BroadcastEvent] = TypeAdapter(BroadcastEvent)


def to_line(event: BroadcastEvent) -> str:
    """One JSON line for ``event`` (no trailing newline): the NDJSON wire format."""
    return BROADCAST_EVENT_ADAPTER.dump_json(event).decode()


def from_line(line: str) -> BroadcastEvent:
    """Parse one NDJSON line back into a validated event."""
    return BROADCAST_EVENT_ADAPTER.validate_json(line)
