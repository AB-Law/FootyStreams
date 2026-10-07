"""Event base, clock and participant models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import MatchId, PlayerId, Pos


class MatchClock(DomainModel):
    """Displayed match clock at emit time."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "period": "S",
        "minute": "S",
        "second": "S",
        "stoppage": "S",
    }

    period: int = Field(ge=1, le=4)
    minute: int = Field(ge=0, le=120)
    second: int = Field(ge=0, le=59)
    stoppage: int = Field(ge=0, default=0)


class Participant(DomainModel):
    """Named participant on an event."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "player_id": "S",
        "role": "S",
    }

    player_id: PlayerId
    role: str = "actor"


class EventBase(DomainModel):
    """Shared fields for every match event."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S",
        "match_id": "S",
        "seq": "S",
        "tick": "S",
        "type": "S",
        "clock": "S",
        "team": "S",
        "participants": "S",
        "pos": "S",
        "caused_by": "S",
        "chain_id": "S",
    }

    id: str
    match_id: MatchId
    seq: int = Field(ge=0)
    tick: int = Field(ge=0)
    type: str
    clock: MatchClock
    team: Literal["home", "away", "none"] = "none"
    participants: tuple[Participant, ...] = ()
    pos: Pos | None = None
    caused_by: str | None = None
    chain_id: str | None = None
