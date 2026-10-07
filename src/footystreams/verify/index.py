"""Shared helpers for the match checks: who an event mentions and a lookup of events by id."""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase
from footystreams.events.types import MatchEvent

PLAYER_FIELDS = (
    "from_player_id",
    "to_player_id",
    "player_id",
    "target_id",
    "keeper_id",
    "scorer_id",
    "assist_id",
    "fouler_id",
    "fouled_id",
    "taker_id",
    "player_off_id",
    "player_on_id",
    "caused_by_player_id",
)


def players_in(event: EventBase) -> set[PlayerId]:
    """Return every player an event names, in participants or in a typed id field."""
    found = {participant.player_id for participant in event.participants}
    for name in PLAYER_FIELDS:
        value = getattr(event, name, None)
        if value is not None:
            found.add(value)
    return found


def index_by_id(events: Sequence[MatchEvent]) -> dict[str, tuple[int, MatchEvent]]:
    """Map event id -> (position in the log, event); the first occurrence wins."""
    index: dict[str, tuple[int, MatchEvent]] = {}
    for position, event in enumerate(events):
        index.setdefault(event.id, (position, event))
    return index
