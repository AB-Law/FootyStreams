"""The channel's own season: a double round robin of the world's clubs, one match at a time."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

DAYS_PER_MATCHDAY = 7
DAYS_PER_SEASON = 365
SEED_STRIDE = 1_000_003
SEASON_STRIDE = 10_007
SEED_MODULUS = 2**31


@dataclass(frozen=True, slots=True)
class Pairing:
    """One fixture of the season: who is at home, who is away, and on which matchday."""

    index: int
    matchday: int
    home_id: str
    away_id: str


def _round(clubs: Sequence[str | None], number: int) -> list[tuple[str, str]]:
    """The pairs of one round by the circle method; the first club stays put, the rest turn."""
    turning = list(clubs[1:])
    shift = number % len(turning)
    order = [clubs[0], *turning[-shift:], *turning[:-shift]] if shift else list(clubs)
    pairs: list[tuple[str, str]] = []
    for place in range(len(order) // 2):
        home, away = order[place], order[len(order) - 1 - place]
        if home is None or away is None:
            continue
        pairs.append((home, away) if (place + number) % 2 == 0 else (away, home))
    return pairs


def season_fixtures(club_ids: Sequence[str]) -> tuple[Pairing, ...]:
    """Every club plays every other home and away; a club never plays twice on a matchday."""
    clubs: list[str | None] = [*sorted(club_ids)]
    if len(clubs) % 2:
        clubs.append(None)
    rounds = [_round(clubs, number) for number in range(len(clubs) - 1)]
    rounds += [[(away, home) for home, away in pairs] for pairs in rounds]
    fixtures: list[Pairing] = []
    for matchday, pairs in enumerate(rounds, start=1):
        for home, away in pairs:
            fixtures.append(Pairing(len(fixtures), matchday, home, away))
    return tuple(fixtures)


def fixture_key(season: int, index: int) -> str:
    """A stable name for a fixture: season 2, fixture 5 is ``s2-f005``."""
    return f"s{season}-f{index:03d}"


def match_seed(world_seed: int, season: int, index: int) -> int:
    """The simulation seed for a fixture: the same fixture always plays out the same way."""
    return (world_seed * SEED_STRIDE + season * SEASON_STRIDE + index) % SEED_MODULUS


def show_date(start: dt.date, season: int, matchday: int) -> dt.date:
    """The in-world date of a matchday: a week on from the one before."""
    days = (season - 1) * DAYS_PER_SEASON + (matchday - 1) * DAYS_PER_MATCHDAY
    return start + dt.timedelta(days=days)
