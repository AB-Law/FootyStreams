"""Standings rows and pure table computation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import ClubId, SeasonId

POINTS_WIN = 3
POINTS_DRAW = 1


class StandingRow(DomainModel):
    """One club's row in a season table."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "season_id": "L",
        "club_id": "L",
        "played": "L",
        "won": "L",
        "drawn": "L",
        "lost": "L",
        "goals_for": "L",
        "goals_against": "L",
        "goal_difference": "L",
        "points": "L",
        "position": "L",
    }

    season_id: SeasonId
    club_id: ClubId
    played: int = Field(ge=0, default=0)
    won: int = Field(ge=0, default=0)
    drawn: int = Field(ge=0, default=0)
    lost: int = Field(ge=0, default=0)
    goals_for: int = Field(ge=0, default=0)
    goals_against: int = Field(ge=0, default=0)
    goal_difference: int = 0
    points: int = Field(ge=0, default=0)
    position: int = Field(ge=1, default=1)


class MatchScore(DomainModel):
    """Minimal result used to recompute standings."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "home_club_id": "L",
        "away_club_id": "L",
        "home_goals": "L",
        "away_goals": "L",
    }

    home_club_id: ClubId
    away_club_id: ClubId
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)


def compute(
    season_id: SeasonId, club_ids: Sequence[ClubId], results: Sequence[MatchScore]
) -> tuple[StandingRow, ...]:
    """Derive ordered standings from completed scores (points, GD, GF)."""
    rows: dict[ClubId, dict[str, int]] = {
        club_id: {
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
        }
        for club_id in club_ids
    }
    for result in results:
        _apply_result(rows, result)
    ordered = sorted(
        rows.items(),
        key=lambda item: (
            -item[1]["points"],
            -(item[1]["goals_for"] - item[1]["goals_against"]),
            -item[1]["goals_for"],
            str(item[0]),
        ),
    )
    return tuple(
        StandingRow(
            season_id=season_id,
            club_id=club_id,
            played=stats["played"],
            won=stats["won"],
            drawn=stats["drawn"],
            lost=stats["lost"],
            goals_for=stats["goals_for"],
            goals_against=stats["goals_against"],
            goal_difference=stats["goals_for"] - stats["goals_against"],
            points=stats["points"],
            position=index,
        )
        for index, (club_id, stats) in enumerate(ordered, start=1)
    )


def _apply_result(rows: dict[ClubId, dict[str, int]], result: MatchScore) -> None:
    home = rows[result.home_club_id]
    away = rows[result.away_club_id]
    home["played"] += 1
    away["played"] += 1
    home["goals_for"] += result.home_goals
    home["goals_against"] += result.away_goals
    away["goals_for"] += result.away_goals
    away["goals_against"] += result.home_goals
    if result.home_goals > result.away_goals:
        home["won"] += 1
        away["lost"] += 1
        home["points"] += POINTS_WIN
    elif result.home_goals < result.away_goals:
        away["won"] += 1
        home["lost"] += 1
        away["points"] += POINTS_WIN
    else:
        home["drawn"] += 1
        away["drawn"] += 1
        home["points"] += POINTS_DRAW
        away["points"] += POINTS_DRAW
