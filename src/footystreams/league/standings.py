"""League table with the full tie-break chain, computed from results.

Order: points, goal difference, goals scored, then the head-to-head mini-league of the tied clubs
(points, goal difference, goals scored), then club id so the order is always total and stable.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.standings import POINTS_DRAW, POINTS_WIN, MatchScore, StandingRow
from footystreams.domain.types import ClubId, SeasonId


@dataclass(slots=True)
class _Tally:
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def points(self) -> int:
        return self.won * POINTS_WIN + self.drawn * POINTS_DRAW

    @property
    def difference(self) -> int:
        return self.goals_for - self.goals_against

    def add(self, scored: int, conceded: int) -> None:
        self.played += 1
        self.goals_for += scored
        self.goals_against += conceded
        if scored > conceded:
            self.won += 1
        elif scored == conceded:
            self.drawn += 1
        else:
            self.lost += 1

    def key(self) -> tuple[int, int, int]:
        """Sort key, larger is better."""
        return (self.points, self.difference, self.goals_for)


def _tally(clubs: Sequence[ClubId], results: Sequence[MatchScore]) -> dict[ClubId, _Tally]:
    tallies: dict[ClubId, _Tally] = defaultdict(_Tally)
    for club in clubs:
        tallies[club] = _Tally()
    for result in results:
        tallies[result.home_club_id].add(result.home_goals, result.away_goals)
        tallies[result.away_club_id].add(result.away_goals, result.home_goals)
    return tallies


def _head_to_head(tied: Sequence[ClubId], results: Sequence[MatchScore]) -> dict[ClubId, _Tally]:
    among = set(tied)
    return _tally(tied, [r for r in results if r.home_club_id in among and r.away_club_id in among])


def _break_ties(tied: list[ClubId], results: Sequence[MatchScore]) -> list[ClubId]:
    if len(tied) == 1:
        return tied
    mini = _head_to_head(tied, results)
    return sorted(tied, key=lambda club: (*(-v for v in mini[club].key()), str(club)))


def table_order(clubs: Sequence[ClubId], results: Sequence[MatchScore]) -> list[ClubId]:
    """Clubs best first under the full tie-break chain."""
    tallies = _tally(clubs, results)
    groups: dict[tuple[int, int, int], list[ClubId]] = defaultdict(list)
    for club, tally in tallies.items():
        groups[tally.key()].append(club)
    ordered: list[ClubId] = []
    for key in sorted(groups, reverse=True):
        ordered.extend(_break_ties(sorted(groups[key]), results))
    return ordered


def compute_table(
    season_id: SeasonId, clubs: Sequence[ClubId], results: Sequence[MatchScore]
) -> tuple[StandingRow, ...]:
    """The standings rows, positions 1..n, from completed results."""
    tallies = _tally(clubs, results)
    return tuple(
        StandingRow(
            season_id=season_id,
            club_id=club,
            played=tallies[club].played,
            won=tallies[club].won,
            drawn=tallies[club].drawn,
            lost=tallies[club].lost,
            goals_for=tallies[club].goals_for,
            goals_against=tallies[club].goals_against,
            goal_difference=tallies[club].difference,
            points=tallies[club].points,
            position=position,
        )
        for position, club in enumerate(table_order(clubs, results), start=1)
    )
