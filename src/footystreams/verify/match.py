"""Match invariants: `verify_match` checks an event log against the catalogue in 10 section 9.

Pure functions returning `Violation`s; the same code serves unit tests, `sim --strict`, soak runs
and the production pre-air gate, so no check is ever re-implemented elsewhere. Codes:

  M01 seq contiguous from 0        M02 time (period, clock, tick) never goes backwards
  M03 ids unique and well formed   M04 score in every context equals the goals so far
  M05 no player on both sheets     M10 positions inside the pitch
  M17 nothing after fulltime but the summary; log starts with a kickoff
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import pairwise

from footystreams.domain.match import MatchSetup, players_on_both_sheets
from footystreams.events.clock import period_elapsed_s
from footystreams.events.open_play import GoalEvent
from footystreams.events.structure import FulltimeEvent, KickoffEvent
from footystreams.events.summary import MatchSummaryEvent
from footystreams.events.types import MatchEvent
from footystreams.verify.violation import Violation

Check = Callable[[Sequence[MatchEvent]], list[Violation]]


def _violation(code: str, message: str, event: MatchEvent | None = None) -> Violation:
    return Violation(code, message, event.id if event is not None else None)


def check_sequence(events: Sequence[MatchEvent]) -> list[Violation]:
    """M01: `seq` is 0, 1, 2, ... in log order."""
    return [
        _violation("M01", f"seq is {event.seq}, expected {index}", event)
        for index, event in enumerate(events)
        if event.seq != index
    ]


def check_ids(events: Sequence[MatchEvent]) -> list[Violation]:
    """M03: ids are unique and equal `{match_id}:{seq:05d}`."""
    found: list[Violation] = []
    seen: set[str] = set()
    for event in events:
        if event.id in seen:
            found.append(_violation("M03", "duplicate event id", event))
        seen.add(event.id)
        if event.id != f"{event.match_id}:{event.seq:05d}":
            found.append(
                _violation("M03", f"id does not match match_id and seq ({event.seq})", event)
            )
    return found


def check_time(events: Sequence[MatchEvent]) -> list[Violation]:
    """M02: (period, clock seconds) and tick never decrease."""
    found: list[Violation] = []
    for previous, current in pairwise(events):
        before = (previous.clock.period, period_elapsed_s(previous.clock))
        after = (current.clock.period, period_elapsed_s(current.clock))
        if after < before:
            found.append(_violation("M02", f"clock went back from {before} to {after}", current))
        elif current.tick < previous.tick:
            found.append(_violation("M02", f"tick went back from {previous.tick}", current))
    return found


def check_scores(events: Sequence[MatchEvent]) -> list[Violation]:
    """M04: every event's context score equals the goals scored up to and including it."""
    found: list[Violation] = []
    home = away = 0
    for event in events:
        if isinstance(event, GoalEvent):
            home += event.team == "home"
            away += event.team == "away"
        if (event.ctx.score_home, event.ctx.score_away) != (home, away):
            found.append(
                _violation(
                    "M04",
                    f"score {event.ctx.score_home}-{event.ctx.score_away}, goals {home}-{away}",
                    event,
                )
            )
        if isinstance(event, FulltimeEvent) and (event.score_home, event.score_away) != (
            home,
            away,
        ):
            found.append(_violation("M04", "fulltime score differs from the goals", event))
        if isinstance(event, MatchSummaryEvent) and (
            event.summary.score_home,
            event.summary.score_away,
        ) != (home, away):
            found.append(_violation("M04", "summary score differs from the goals", event))
    return found


def check_positions(events: Sequence[MatchEvent]) -> list[Violation]:
    """M10: every position lies inside the unit square."""
    return [
        _violation("M10", f"position ({event.pos.x}, {event.pos.y}) is outside the pitch", event)
        for event in events
        if event.pos is not None and not (0.0 <= event.pos.x <= 1.0 and 0.0 <= event.pos.y <= 1.0)
    ]


def check_ending(events: Sequence[MatchEvent]) -> list[Violation]:
    """M17: starts with a kickoff; after fulltime only the summary, and it is last."""
    found: list[Violation] = []
    if events and not isinstance(events[0], KickoffEvent):
        found.append(_violation("M17", "the log does not start with a kickoff", events[0]))
    after_fulltime = False
    for index, event in enumerate(events):
        if after_fulltime and not isinstance(event, MatchSummaryEvent):
            found.append(_violation("M17", "event after fulltime", event))
        if isinstance(event, MatchSummaryEvent) and index != len(events) - 1:
            found.append(_violation("M17", "match_summary is not the last event", event))
        after_fulltime = after_fulltime or isinstance(event, FulltimeEvent)
    return found


def check_rosters(setup: MatchSetup) -> list[Violation]:
    """M05: no player appears on both sheets."""
    return [
        Violation("M05", "player is on both teams", player_id)
        for player_id in players_on_both_sheets(setup)
    ]


_EVENT_CHECKS: tuple[Check, ...] = (
    check_sequence,
    check_ids,
    check_time,
    check_scores,
    check_positions,
    check_ending,
)


def verify_match(events: Sequence[MatchEvent], setup: MatchSetup | None = None) -> list[Violation]:
    """Return every violated match invariant (empty when the log is sound).

    `setup` enables the roster checks; the log checks need only the events.
    """
    found = [violation for check in _EVENT_CHECKS for violation in check(events)]
    if setup is not None:
        found.extend(check_rosters(setup))
    return found
