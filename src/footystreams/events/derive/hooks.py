"""Narrative hooks: deterministic story seeds from the finished match (docs/design/03 section 5).

A hook names a kind of story (a late winner, a comeback, a hat-trick, ...), the events behind it
and a magnitude; `text_key` is a template key, never prose. Rules look only at the log and the
stats, so the same match always yields the same hooks.
"""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.events.clock import match_elapsed_s
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.summary import PlayerMatchStats, TeamStats
from footystreams.events.summary_rows import Hook
from footystreams.events.types import MatchEvent

LATE_WINNER_FROM_MINUTE = 80
RED_CARD_EARLY_MINUTE = 75
HEROICS_SAVES = 6
HEROICS_MAX_CONCEDED = 1
DOMINANT_XG = 2.0
DOMINANT_RATIO = 2.0
HAT_TRICK_GOALS = 3
_SECONDS_PER_MINUTE = 60
_MATCH_MINUTES = 90
_PRECISION = 3


def _hook(kind: str, event_ids: Sequence[str], magnitude: float) -> Hook:
    return Hook(
        kind=kind,
        event_ids=tuple(event_ids),
        magnitude=round(magnitude, _PRECISION),
        text_key=f"hook.{kind}",
    )


def decisive_goal(goals: Sequence[GoalEvent], winner: str) -> tuple[GoalEvent | None, int]:
    """Return the goal that put the winner ahead for good, and the deepest deficit it overcame."""
    score = {"home": 0, "away": 0}
    other = "away" if winner == "home" else "home"
    decisive, deficit = None, 0
    for goal in goals:
        before_ahead = score[winner] > score[other]
        score[goal.team] += 1
        deficit = max(deficit, score[other] - score[winner])
        if not before_ahead and score[winner] > score[other]:
            decisive = goal
    return decisive, deficit


def _winner_hooks(goals: Sequence[GoalEvent], winner: str) -> list[Hook]:
    decisive, deficit = decisive_goal(goals, winner)
    if decisive is None:
        return []
    minute = match_elapsed_s(decisive.clock) / _SECONDS_PER_MINUTE
    found = []
    if minute >= LATE_WINNER_FROM_MINUTE:
        found.append(
            _hook("late_winner", [decisive.id], (minute - LATE_WINNER_FROM_MINUTE + 1) / 11.0)
        )
    if deficit > 0:
        found.append(_hook("comeback", [decisive.id], float(deficit)))
    return found


def _hat_tricks(goals: Sequence[GoalEvent]) -> list[Hook]:
    by_scorer: dict[str, list[str]] = {}
    for goal in goals:
        if not goal.own_goal:
            by_scorer.setdefault(goal.scorer_id, []).append(goal.id)
    return [
        _hook("hat_trick", ids, float(len(ids)))
        for _, ids in sorted(by_scorer.items())
        if len(ids) >= HAT_TRICK_GOALS
    ]


def _red_card_turning_points(events: Sequence[MatchEvent], goal_difference: int) -> list[Hook]:
    found = []
    for event in events:
        if not (isinstance(event, CardEvent) and event.colour != "yellow"):
            continue
        minute = match_elapsed_s(event.clock) / _SECONDS_PER_MINUTE
        lost = (goal_difference < 0) if event.team == "home" else (goal_difference > 0)
        if lost and minute < RED_CARD_EARLY_MINUTE:
            found.append(_hook("red_card_turning_point", [event.id], 1.0 - minute / _MATCH_MINUTES))
    return found


def _keeper_heroics(rows: Sequence[PlayerMatchStats]) -> list[Hook]:
    return [
        _hook("goalkeeper_heroics", [], row.saves / 10.0)
        for row in rows
        if row.saves >= HEROICS_SAVES and row.goals_conceded <= HEROICS_MAX_CONCEDED
    ]


def _dominant_unrewarded(home: TeamStats, away: TeamStats, goal_difference: int) -> list[Hook]:
    found = []
    for stats, rival, won in (
        (home, away, goal_difference > 0),
        (away, home, goal_difference < 0),
    ):
        if not won and stats.xg >= DOMINANT_XG and stats.xg >= DOMINANT_RATIO * rival.xg:
            found.append(_hook("dominant_unrewarded", [], stats.xg - rival.xg))
    return found


def narrative_hooks(
    events: Sequence[MatchEvent],
    rows: Sequence[PlayerMatchStats],
    teams: tuple[TeamStats, TeamStats],
    *,
    is_derby: bool,
) -> tuple[Hook, ...]:
    """Return the match's story seeds in a fixed order (winner stories first)."""
    goals = [event for event in events if isinstance(event, GoalEvent) and event.team != "none"]
    home_goals = sum(goal.team == "home" for goal in goals)
    difference = home_goals - (len(goals) - home_goals)
    found: list[Hook] = []
    if difference != 0:
        found.extend(_winner_hooks(goals, "home" if difference > 0 else "away"))
    found.extend(_hat_tricks(goals))
    found.extend(_red_card_turning_points(events, difference))
    found.extend(_keeper_heroics(rows))
    found.extend(_dominant_unrewarded(teams[0], teams[1], difference))
    if is_derby:
        found.append(_hook("derby_result", [], 1.0))
    return tuple(found)
