"""Post-match ratings (3.0-10.0) and the player of the match, as a pure function of the stats.

A rating starts at 6.0 and adds position-weighted contributions (docs/design/03 section 5):
goals, assists, chance creation, key passes, winning the ball, passing above par, saves, clean
sheets, minus goals conceded, cards and defeat. Players with under 20 minutes regress toward 6.
Ratings are recomputed from the player stats, which are recomputed from the log.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.types import PlayerId
from footystreams.events.summary import PlayerMatchStats, PlayerRating

BASE = 6.0
LOW = 3.0
HIGH = 10.0
REGRESS_MINUTES = 20
PAR_ACCURACY = 0.80
MIN_PASSES_RATED = 15
PASSING_SWING = 2.0
PASSING_CAP = 0.5
KEY_PASS_CAP = 0.6
_PRECISION = 2


@dataclass(frozen=True, slots=True)
class _Weights:
    """How much one unit of each contribution is worth for a position group."""

    goal: float
    tackle: float
    interception: float
    clearance: float
    dribble: float
    clean_sheet: float


_GROUPS: dict[str, _Weights] = {
    "GK": _Weights(0.6, 0.0, 0.0, 0.01, 0.0, 0.3),
    "DF": _Weights(0.6, 0.10, 0.10, 0.03, 0.04, 0.3),
    "MF": _Weights(0.9, 0.10, 0.08, 0.01, 0.06, 0.1),
    "FW": _Weights(0.9, 0.05, 0.05, 0.01, 0.06, 0.0),
}
_GROUP_OF = {
    "GK": "GK",
    "CB": "DF", "RB": "DF", "LB": "DF", "RWB": "DF", "LWB": "DF",
    "DM": "MF", "CM": "MF", "AM": "MF", "RM": "MF", "LM": "MF",
    "RW": "FW", "LW": "FW", "SS": "FW", "ST": "FW",
}  # fmt: skip
_ASSIST = 0.55
_CREATION = 0.4
_KEY_PASS = 0.15
_SAVE = 0.15
_CONCEDED = 0.3
_YELLOW = 0.3
_RED = 1.0
_RESULT = 0.25


def _components(row: PlayerMatchStats, result: int) -> dict[str, float]:
    """Return each contribution to the rating before clamping (`result` is +1, 0 or -1)."""
    weights = _GROUPS[_GROUP_OF.get(row.position, "MF")]
    keeper = _GROUP_OF.get(row.position) == "GK"
    accuracy = row.passes_completed / row.passes if row.passes else PAR_ACCURACY
    passing = (
        max(-PASSING_CAP, min(PASSING_CAP, (accuracy - PAR_ACCURACY) * PASSING_SWING))
        if row.passes >= MIN_PASSES_RATED
        else 0.0
    )
    return {
        "goals": weights.goal * row.goals,
        "assists": _ASSIST * row.assists,
        "creation": _CREATION * (row.xg + row.xa),
        "key_passes": min(KEY_PASS_CAP, _KEY_PASS * row.key_passes),
        "dribbling": weights.dribble * row.dribbles_won,
        "tackling": weights.tackle * row.tackles_won,
        "interceptions": weights.interception * row.interceptions,
        "clearances": weights.clearance * row.clearances,
        "passing": passing,
        "saves": _SAVE * row.saves,
        "conceded": -_CONCEDED * row.goals_conceded if keeper else 0.0,
        "clean_sheet": weights.clean_sheet if row.clean_sheet else 0.0,
        "cards": -_YELLOW * row.yellows - _RED * row.reds,
        "result": _RESULT * result,
    }


def rate_player(row: PlayerMatchStats, result: int) -> PlayerRating:
    """Rate one player given his stats and his side's result (+1 win, 0 draw, -1 defeat)."""
    parts = _components(row, result)
    raw = BASE + sum(parts.values())
    if row.minutes < REGRESS_MINUTES:
        raw = BASE + (raw - BASE) * row.minutes / REGRESS_MINUTES
    rating = round(max(LOW, min(HIGH, raw)), 1)
    breakdown = {name: round(value, _PRECISION) for name, value in parts.items() if value}
    return PlayerRating(player_id=row.player_id, rating=rating, breakdown=breakdown)


def rate_match(
    rows: Sequence[PlayerMatchStats], sides: Mapping[PlayerId, str], goal_difference: int
) -> tuple[PlayerRating, ...]:
    """Rate every row; `goal_difference` is home minus away and `sides` maps players to teams."""
    sign = (goal_difference > 0) - (goal_difference < 0)
    return tuple(
        rate_player(row, sign if sides[row.player_id] == "home" else -sign) for row in rows
    )


def player_of_the_match(
    rows: Sequence[PlayerMatchStats], ratings: Sequence[PlayerRating]
) -> PlayerId | None:
    """Return the best-rated player; ties go to more goal involvements, then chance creation."""
    if not rows:
        return None
    best = max(
        zip(rows, ratings, strict=True),
        key=lambda pair: (pair[1].rating, pair[0].goals + pair[0].assists, pair[0].xg + pair[0].xa),
    )
    return best[0].player_id
