"""``MatchSample``: the handful of numbers one finished match contributes to the balance metrics.

A sample is small and picklable so worker processes can send thousands back cheaply. Everything
comes from the event log and summary, so a metric can never disagree with what a viewer saw.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.events.discipline import InjuryEvent, SubstitutionEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.restarts import PenaltyEvent
from footystreams.events.result import MatchResult
from footystreams.events.structure import AddedTimeEvent
from footystreams.events.summary import TeamStats

FIRST_HALF, SECOND_HALF = 1, 2
LATE_MINUTE = 75  # "the last 15 minutes" of regulation, stoppage time included
INJURY_REASON = "injury"


@dataclass(frozen=True, slots=True)
class SideSample:
    """One team's numbers in one match."""

    goals: int
    shots: int
    on_target: int
    passes: int
    passes_completed: float
    possession: float
    fouls: int
    corners: int
    offsides: int
    yellows: int
    reds: int
    substitutions: int


@dataclass(frozen=True, slots=True)
class MatchSample:
    """Both teams plus the match-level facts; ``gap`` is home rating minus away rating."""

    home: SideSample
    away: SideSample
    gap: float
    penalties: int
    penalties_scored: int
    injuries: int
    goals_second_half: int
    goals_late: int
    added_first_half: int
    added_second_half: int
    early_tactical_subs: int

    @property
    def goals(self) -> int:
        """Goals by both teams."""
        return self.home.goals + self.away.goals


def _side(stats: TeamStats, goals: int, substitutions: int) -> SideSample:
    return SideSample(
        goals=goals,
        shots=stats.shots,
        on_target=stats.shots_on_target,
        passes=stats.passes,
        passes_completed=stats.pass_accuracy * stats.passes,
        possession=stats.possession,
        fouls=stats.fouls,
        corners=stats.corners,
        offsides=stats.offsides,
        yellows=stats.yellows,
        reds=stats.reds,
        substitutions=substitutions,
    )


def sample_from(result: MatchResult, gap: float) -> MatchSample:
    """Reduce a finished match to its sample; ``gap`` is the home side's rating advantage."""
    goals_second_half = goals_late = injuries = early_tactical = 0
    penalties = penalties_scored = 0
    subs = {"home": 0, "away": 0}
    added = {FIRST_HALF: 0, SECOND_HALF: 0}
    for event in result.events:
        if isinstance(event, GoalEvent):
            goals_second_half += event.clock.period == SECOND_HALF
            goals_late += event.clock.period == SECOND_HALF and event.clock.minute >= LATE_MINUTE
        elif isinstance(event, PenaltyEvent):
            penalties += 1
            penalties_scored += event.outcome == "goal"
        elif isinstance(event, InjuryEvent):
            injuries += 1
        elif isinstance(event, SubstitutionEvent):
            subs[event.team if event.team in subs else "home"] += 1
            early_tactical += event.clock.period == FIRST_HALF and event.reason != INJURY_REASON
        elif isinstance(event, AddedTimeEvent) and event.clock.period in added:
            added[event.clock.period] = event.minutes
    summary = result.summary
    return MatchSample(
        home=_side(summary.team_stats_home, summary.score_home, subs["home"]),
        away=_side(summary.team_stats_away, summary.score_away, subs["away"]),
        gap=gap,
        penalties=penalties,
        penalties_scored=penalties_scored,
        injuries=injuries,
        goals_second_half=goals_second_half,
        goals_late=goals_late,
        added_first_half=added[FIRST_HALF],
        added_second_half=added[SECOND_HALF],
        early_tactical_subs=early_tactical,
    )
