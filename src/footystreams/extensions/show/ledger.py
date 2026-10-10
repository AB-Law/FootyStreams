"""What the desk can say about the football it has aired: tables, form, head-to-heads, scorers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from footystreams.extensions.show.bible import Result

POINTS_WIN = 3
POINTS_DRAW = 1
FORM_LENGTH = 5
MEETINGS_SHOWN = 4


@dataclass(frozen=True, slots=True)
class TableRow:
    """One club's line in the table."""

    club_id: str
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int

    @property
    def points(self) -> int:
        """Three for a win, one for a draw."""
        return self.won * POINTS_WIN + self.drawn * POINTS_DRAW

    @property
    def goal_difference(self) -> int:
        """Goals for minus goals against."""
        return self.goals_for - self.goals_against


def season_results(results: Iterable[Result], season: int) -> list[Result]:
    """The results of one season, in the order they were aired."""
    return [result for result in results if result.season == season]


@dataclass(slots=True)
class _Tally:
    """A club's running totals while the table is built."""

    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    def add(self, own: int, other: int) -> None:
        """Count one match from this club's side."""
        self.played += 1
        self.won += own > other
        self.drawn += own == other
        self.lost += own < other
        self.goals_for += own
        self.goals_against += other


def table(results: Sequence[Result], names: Mapping[str, str]) -> list[TableRow]:
    """The league table over ``results`` for every club in ``names``, best first."""
    tallies = {club_id: _Tally() for club_id in names}
    for result in results:
        tallies[result.home_id].add(result.home_goals, result.away_goals)
        tallies[result.away_id].add(result.away_goals, result.home_goals)
    rows = [
        TableRow(
            club_id,
            names[club_id],
            tally.played,
            tally.won,
            tally.drawn,
            tally.lost,
            tally.goals_for,
            tally.goals_against,
        )
        for club_id, tally in tallies.items()
    ]
    return sorted(
        rows, key=lambda row: (-row.points, -row.goal_difference, -row.goals_for, row.name)
    )


def position(rows: Sequence[TableRow], club_id: str) -> int:
    """A club's place in the table, from 1."""
    return next(index for index, row in enumerate(rows, start=1) if row.club_id == club_id)


def _letter(result: Result, club_id: str) -> str:
    own, other = (
        (result.home_goals, result.away_goals)
        if result.home_id == club_id
        else (result.away_goals, result.home_goals)
    )
    return "W" if own > other else "D" if own == other else "L"


def form(results: Sequence[Result], club_id: str) -> str:
    """The club's last five results, oldest first, as letters: ``WDLWW``."""
    played = [result for result in results if club_id in (result.home_id, result.away_id)]
    return "".join(_letter(result, club_id) for result in played[-FORM_LENGTH:])


def meetings(results: Sequence[Result], club_a: str, club_b: str) -> list[Result]:
    """The latest meetings of two clubs on the desk, newest last."""
    pair = {club_a, club_b}
    found = [result for result in results if {result.home_id, result.away_id} == pair]
    return found[-MEETINGS_SHOWN:]


def scoreline(result: Result) -> str:
    """``Home 2-1 Away`` for a result."""
    return f"{result.home_name} {result.home_goals}-{result.away_goals} {result.away_name}"


def top_scorers(results: Iterable[Result], limit: int = 3) -> list[tuple[str, int]]:
    """The players with most goals across ``results``, as ``(name, goals)``."""
    goals: Counter[str] = Counter()
    for result in results:
        for scorer in result.scorers:
            goals[scorer.name] += scorer.goals
    return sorted(goals.items(), key=lambda item: (-item[1], item[0]))[:limit]


def biggest_win(results: Iterable[Result]) -> Result | None:
    """The result with the widest margin, the earliest if tied."""
    pool = list(results)
    if not pool:
        return None
    return max(pool, key=lambda result: abs(result.home_goals - result.away_goals))
