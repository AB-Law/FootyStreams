"""Invariants about events as data and the summary that closes the log (M13-M16, M18).

M13 every event survives a round trip through its JSON form (it is a valid `MatchEvent`)
M14 the summary is recomputable from the events (and the setup) it summarises
M15 ratings lie in [3, 10] and the rows agree with the ratings
M16 the summary's `log_digest` is the digest of every event before it
M18 probabilities, xG and the context's unit-range numbers stay in range
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from footystreams.domain.match import MatchSetup
from footystreams.events.derive.summary import SummaryInputs, build_summary
from footystreams.events.digest import log_digest
from footystreams.events.open_play import ShotEvent
from footystreams.events.summary import MatchSummary, MatchSummaryEvent
from footystreams.events.types import MATCH_EVENT_ADAPTER, MatchEvent
from footystreams.verify.violation import Violation

RATING_LOW = 3.0
RATING_HIGH = 10.0


def _summary_of(events: Sequence[MatchEvent]) -> tuple[int, MatchSummary] | None:
    """Return the position and payload of the summary event, if the log ends with one."""
    if events and isinstance(events[-1], MatchSummaryEvent):
        return len(events) - 1, events[-1].summary
    return None


def check_events_validate(events: Sequence[MatchEvent]) -> list[Violation]:
    """M13: each event rebuilds from its own JSON into an equal, valid event."""
    found: list[Violation] = []
    for event in events:
        try:
            rebuilt = MATCH_EVENT_ADAPTER.validate_json(event.model_dump_json())
        except ValidationError as error:
            found.append(
                Violation("M13", f"event does not validate: {error.error_count()}", event.id)
            )
            continue
        if rebuilt != event:
            found.append(Violation("M13", "event changes in a JSON round trip", event.id))
    return found


def check_summary_recomputes(events: Sequence[MatchEvent], setup: MatchSetup) -> list[Violation]:
    """M14: rebuilding the summary from the events gives the stored summary, field by field."""
    located = _summary_of(events)
    if located is None:
        return []
    position, stored = located
    inputs = SummaryInputs(
        seed=stored.seed,
        config_hash=stored.config_hash,
        log_digest=stored.log_digest,
        injuries=stored.injuries,
        end_exhaustion={row.player_id: row.end_exhaustion for row in stored.player_stats},
    )
    subject = events[position].id
    try:
        rebuilt = build_summary(events[:position], setup, inputs)
    except ValidationError as error:
        return [
            Violation("M14", f"summary cannot be rebuilt: {error.error_count()} errors", subject)
        ]
    return [
        Violation("M14", f"summary field {name} is not recomputable from the events", subject)
        for name in MatchSummary.model_fields
        if getattr(rebuilt, name) != getattr(stored, name)
    ]


def check_ratings(events: Sequence[MatchEvent]) -> list[Violation]:
    """M15: every rating is within [3, 10] and the player rows carry the same numbers."""
    located = _summary_of(events)
    if located is None:
        return []
    position, summary = located
    subject = events[position].id
    found = [
        Violation("M15", f"rating {rating.rating} of {rating.player_id} is out of range", subject)
        for rating in summary.ratings
        if not RATING_LOW <= rating.rating <= RATING_HIGH
    ]
    by_player = {rating.player_id: rating.rating for rating in summary.ratings}
    found.extend(
        Violation("M15", f"player row of {row.player_id} disagrees with its rating", subject)
        for row in summary.player_stats
        if by_player.get(row.player_id, row.rating) != row.rating
    )
    return found


def check_digest(events: Sequence[MatchEvent]) -> list[Violation]:
    """M16: the summary's digest is the digest of the events before it."""
    located = _summary_of(events)
    if located is None:
        return []
    position, summary = located
    if log_digest(events[:position]) == summary.log_digest:
        return []
    return [Violation("M16", "log_digest does not match the events", events[position].id)]


def check_ranges(events: Sequence[MatchEvent]) -> list[Violation]:
    """M18: xG, momentum, intensity and significance are inside their ranges."""
    found: list[Violation] = []
    for event in events:
        context = event.ctx
        if not (
            -1.0 <= context.momentum <= 1.0
            and 0.0 <= context.intensity <= 1.0
            and 0.0 <= context.significance <= 1.0
        ):
            found.append(Violation("M18", "context number out of range", event.id))
        if isinstance(event, ShotEvent) and not 0.0 <= event.xg <= 1.0:
            found.append(Violation("M18", f"xG {event.xg} is not a probability", event.id))
    return found
