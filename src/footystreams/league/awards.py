"""Season totals per player and the end-of-season awards (champion, top scorer, best player)."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.ids import derive_id
from footystreams.domain.mood import (
    ModifierSource,
    ModifierVisibility,
    StateKind,
    StateModifier,
    WorldEvent,
)
from footystreams.domain.standings import StandingRow
from footystreams.domain.types import EntityKind, EntityRef, Id, PlayerId
from footystreams.events.summary import MatchSummary
from footystreams.league.modifiers import ModifierSpec, new_modifier
from footystreams.league.mood_config import MoodConfig

TROPHY_STRENGTH = 0.9
AWARD_STRENGTH = 0.8


@dataclass(slots=True)
class SeasonTotals:
    """What one player did over a season."""

    appearances: int = 0
    minutes: int = 0
    goals: int = 0
    rating_sum: float = 0.0

    @property
    def average_rating(self) -> float:
        """Mean match rating (0.0 with no appearances)."""
        return self.rating_sum / self.appearances if self.appearances else 0.0


def season_totals(summaries: Iterable[MatchSummary]) -> dict[PlayerId, SeasonTotals]:
    """Fold the match summaries of a season into per-player totals."""
    totals: dict[PlayerId, SeasonTotals] = defaultdict(SeasonTotals)
    for summary in summaries:
        for row in summary.player_stats:
            total = totals[PlayerId(row.player_id)]
            total.appearances += 1
            total.minutes += row.minutes
            total.goals += row.goals
            total.rating_sum += row.rating
    return dict(totals)


def _event(
    kind: str, subject: EntityRef, today: dt.date, facts: Mapping[str, str | int | float | bool]
) -> WorldEvent:
    return WorldEvent(
        id=Id(derive_id("world_event", subject.id, today.isoformat(), kind)),
        date=today,
        kind=kind,
        participants=(subject,),
        facts=facts,
        visibility=ModifierVisibility.PUBLIC,
        origin="rule",
    )


def _player_ref(player_id: PlayerId) -> EntityRef:
    return EntityRef(kind=EntityKind.PLAYER, id=Id(player_id))


def top_scorer(totals: Mapping[PlayerId, SeasonTotals]) -> PlayerId | None:
    """Most goals; ties go to fewer minutes, then the lower id."""
    candidates = [(pid, t) for pid, t in totals.items() if t.goals > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (-item[1].goals, item[1].minutes, item[0]))[0]


def best_player(totals: Mapping[PlayerId, SeasonTotals], min_appearances: int) -> PlayerId | None:
    """Highest average rating among players with enough appearances."""
    candidates = [(pid, t) for pid, t in totals.items() if t.appearances >= min_appearances]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (-item[1].average_rating, item[0]))[0]


def season_awards(
    table: Sequence[StandingRow],
    totals: Mapping[PlayerId, SeasonTotals],
    context: tuple[str, dt.date, int],
) -> list[WorldEvent]:
    """Champion, top scorer and player of the season; ``context`` is (label, date, min apps)."""
    label, today, min_appearances = context
    champion = table[0]
    events = [
        _event(
            "league_champion",
            EntityRef(kind=EntityKind.CLUB, id=Id(champion.club_id)),
            today,
            {"season": label, "points": champion.points},
        )
    ]
    scorer = top_scorer(totals)
    if scorer is not None:
        facts: dict[str, str | int | float | bool] = {
            "season": label,
            "goals": totals[scorer].goals,
        }
        events.append(_event("top_scorer", _player_ref(scorer), today, facts))
    best = best_player(totals, min_appearances)
    if best is not None:
        facts = {"season": label, "rating": round(totals[best].average_rating, 2)}
        events.append(_event("player_of_the_season", _player_ref(best), today, facts))
    return events


def award_modifiers(
    winners: Mapping[StateKind, Sequence[PlayerId]], today: dt.date, mood: MoodConfig
) -> list[StateModifier]:
    """Glow for the champion's players (trophy) and for the individual award winners."""
    source = ModifierSource(origin="rule")
    strengths = {StateKind.TROPHY_GLOW: TROPHY_STRENGTH, StateKind.AWARD_GLOW: AWARD_STRENGTH}
    return [
        new_modifier(ModifierSpec(kind, pid, strengths[kind], source), today, mood)
        for kind in sorted(winners, key=lambda k: k.value)
        for pid in sorted(winners[kind])
    ]
