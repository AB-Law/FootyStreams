"""Sequencing rules (M12, docs/design/03 section 4), checked through `caused_by` links.

- every `caused_by` names an earlier event
- a shot that scores is immediately followed by its goal; a saved shot by its save
- a goal comes from a scoring shot or penalty; a save from a saved shot or penalty
- a penalty that scores is immediately followed by its goal
- a card follows the foul of the booked player; a free kick follows a foul or an offside; a
  penalty follows a foul; an offside follows a pass; a foul follows its tackle
"""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.events.base import EventBase
from footystreams.events.discipline import CardEvent, FoulEvent
from footystreams.events.open_play import GoalEvent, OffsideEvent, SaveEvent, ShotEvent, TackleEvent
from footystreams.events.restarts import FreeKickEvent, PenaltyEvent
from footystreams.events.types import MatchEvent
from footystreams.verify.index import index_by_id
from footystreams.verify.violation import Violation

Index = dict[str, tuple[int, MatchEvent]]


def _cause(event: EventBase, index: Index, position: int) -> MatchEvent | None:
    """Return the earlier event this one names as its cause, if it names a valid one."""
    if event.caused_by is None:
        return None
    entry = index.get(event.caused_by)
    return entry[1] if entry is not None and entry[0] < position else None


def _check_links(events: Sequence[MatchEvent], index: Index) -> list[Violation]:
    return [
        Violation("M12", f"caused_by {event.caused_by} is not an earlier event", event.id)
        for position, event in enumerate(events)
        if event.caused_by is not None and _cause(event, index, position) is None
    ]


def _expects(event: MatchEvent, cause: MatchEvent | None) -> str | None:
    """Return a complaint when `event` has the wrong kind of cause (None means fine)."""
    if isinstance(event, CardEvent) and not (
        isinstance(cause, FoulEvent) and cause.fouler_id == event.player_id
    ):
        return "card is not caused by the foul of the booked player"
    if isinstance(event, FreeKickEvent) and not isinstance(cause, FoulEvent | OffsideEvent):
        return "free kick is not caused by a foul or an offside"
    if isinstance(event, PenaltyEvent) and not isinstance(cause, FoulEvent):
        return "penalty is not caused by a foul"
    if isinstance(event, OffsideEvent) and cause is None:
        return "offside has no pass as its cause"
    if isinstance(event, FoulEvent) and not isinstance(cause, TackleEvent):
        return "foul is not caused by its tackle"
    return None


def _check_causes(events: Sequence[MatchEvent], index: Index) -> list[Violation]:
    found = []
    for position, event in enumerate(events):
        problem = _expects(event, _cause(event, index, position))
        if problem is not None:
            found.append(Violation("M12", problem, event.id))
    return found


def _follows(events: Sequence[MatchEvent], position: int, kind: type) -> bool:
    if position + 1 >= len(events):
        return False
    following = events[position + 1]
    return isinstance(following, kind) and following.caused_by == events[position].id


def _check_outcomes(events: Sequence[MatchEvent]) -> list[Violation]:
    found = []
    for position, event in enumerate(events):
        scored = isinstance(event, ShotEvent | PenaltyEvent) and event.outcome == "goal"
        saved = isinstance(event, ShotEvent | PenaltyEvent) and event.outcome == "saved"
        if scored and not _follows(events, position, GoalEvent):
            found.append(
                Violation("M12", "a scoring shot or penalty is not followed by its goal", event.id)
            )
        if saved and not _follows(events, position, SaveEvent):
            found.append(
                Violation("M12", "a saved shot or penalty is not followed by its save", event.id)
            )
    return found


def _check_origins(events: Sequence[MatchEvent], index: Index) -> list[Violation]:
    found = []
    for position, event in enumerate(events):
        if not isinstance(event, GoalEvent | SaveEvent):
            continue
        reference = event.shot_event_id
        entry = index.get(reference) if reference is not None else None
        wanted = "goal" if isinstance(event, GoalEvent) else "saved"
        origin = entry[1] if entry is not None and entry[0] < position else None
        if not (isinstance(origin, ShotEvent | PenaltyEvent) and origin.outcome == wanted):
            found.append(Violation("M12", f"{event.type} has no matching {wanted} shot", event.id))
    return found


def check_sequencing(events: Sequence[MatchEvent]) -> list[Violation]:
    """M12: the sequencing rules of docs/design/03 section 4 that the sim currently emits."""
    index = index_by_id(events)
    return [
        *_check_links(events, index),
        *_check_causes(events, index),
        *_check_outcomes(events),
        *_check_origins(events, index),
    ]
