"""The non-causal annotation pass: facts that need the whole match (docs/design/03 section 6).

`annotate(events)` looks at a finished log and says which goal won it, which was a late winner or
completed a comeback, which moments turned it and which goal was the best. It is for replays,
highlight reels and memory creation, which run after the match; the live narrator never reads it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.events.clock import match_elapsed_s
from footystreams.events.derive.hooks import (
    LATE_WINNER_FROM_MINUTE,
    RED_CARD_EARLY_MINUTE,
    decisive_goal,
)
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.structure import FrameEvent
from footystreams.events.types import MatchEvent

_SECONDS_PER_MINUTE = 60
_WINNER_WEIGHT = 0.3
_COMEBACK_WEIGHT = 0.2
_LATE_WEIGHT = 0.1
_TURNING_WEIGHT = 0.2
_PRECISION = 3


@dataclass(frozen=True, slots=True)
class EventAnnotation:
    """What hindsight says about one event."""

    event_id: str
    is_winning_goal: bool = False
    was_turning_point: bool = False
    is_late_winner: bool = False
    comeback_completed: bool = False
    goal_of_the_match: bool = False
    narrative_weight: float = 0.0


def _goals(events: Sequence[MatchEvent]) -> list[GoalEvent]:
    return [e for e in events if isinstance(e, GoalEvent) and e.team != "none"]


def _winning_goal(goals: Sequence[GoalEvent]) -> tuple[GoalEvent | None, int]:
    """Return the goal that decided the match (None for a draw) and the deficit it overcame."""
    home = sum(goal.team == "home" for goal in goals)
    difference = home - (len(goals) - home)
    if difference == 0:
        return None, 0
    return decisive_goal(goals, "home" if difference > 0 else "away")


def _turning_dismissals(events: Sequence[MatchEvent], goals: Sequence[GoalEvent]) -> set[str]:
    """Return the early dismissals of the side that went on to lose."""
    home = sum(goal.team == "home" for goal in goals)
    difference = home - (len(goals) - home)
    found = set()
    for event in events:
        if not (isinstance(event, CardEvent) and event.colour != "yellow"):
            continue
        minute = match_elapsed_s(event.clock) / _SECONDS_PER_MINUTE
        lost = (difference < 0) if event.team == "home" else (difference > 0)
        if lost and minute < RED_CARD_EARLY_MINUTE:
            found.add(event.id)
    return found


def _weight(event: MatchEvent, flags: dict[str, bool]) -> float:
    weight = event.ctx.significance
    weight += _WINNER_WEIGHT * flags["winning"]
    weight += _COMEBACK_WEIGHT * flags["comeback"]
    weight += _LATE_WEIGHT * flags["late"]
    weight += _TURNING_WEIGHT * flags["turning"]
    return round(min(1.0, weight), _PRECISION)


def annotate(events: Sequence[MatchEvent]) -> list[EventAnnotation]:
    """Return one annotation per event (tracking frames excluded), in log order."""
    plays = [event for event in events if not isinstance(event, FrameEvent)]
    goals = _goals(plays)
    winner, deficit = _winning_goal(goals)
    turning = _turning_dismissals(plays, goals)
    if winner is not None:
        turning.add(winner.id)
    annotations = []
    for event in plays:
        is_winner = winner is not None and event.id == winner.id
        late = is_winner and match_elapsed_s(event.clock) >= LATE_WINNER_FROM_MINUTE * 60
        flags = {
            "winning": is_winner,
            "comeback": is_winner and deficit > 0,
            "late": late,
            "turning": event.id in turning,
        }
        annotations.append(
            EventAnnotation(
                event_id=event.id,
                is_winning_goal=is_winner,
                was_turning_point=flags["turning"],
                is_late_winner=late,
                comeback_completed=flags["comeback"],
                narrative_weight=_weight(event, flags),
            )
        )
    return _with_goal_of_the_match(annotations, goals)


def _with_goal_of_the_match(
    annotations: list[EventAnnotation], goals: Sequence[GoalEvent]
) -> list[EventAnnotation]:
    """Mark the goal with the greatest narrative weight (the earliest on a tie)."""
    goal_ids = {goal.id for goal in goals}
    candidates = [a for a in annotations if a.event_id in goal_ids]
    if not candidates:
        return annotations
    best = max(candidates, key=lambda a: a.narrative_weight)
    return [
        EventAnnotation(
            event_id=a.event_id,
            is_winning_goal=a.is_winning_goal,
            was_turning_point=a.was_turning_point,
            is_late_winner=a.is_late_winner,
            comeback_completed=a.comeback_completed,
            goal_of_the_match=a.event_id == best.event_id,
            narrative_weight=a.narrative_weight,
        )
        for a in annotations
    ]
