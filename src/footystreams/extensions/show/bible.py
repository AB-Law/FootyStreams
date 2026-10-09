"""The show bible: everything the desk remembers between segments, stored as one JSON document.

It is the show's own state, never the world's: the results of the fixtures it has aired, what each
host remembers, predictions waiting to be settled, and where the rundown is. Memories use the
world's ``MemoryRecord`` shape so they can move into the database later.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

from pydantic import Field

from footystreams.domain.memory import MemoryRecord
from footystreams.extensions.show.models import Pick, ShowModel

BIBLE_VERSION = 1
SEASONS_KEPT = 3
LAST_LINES_KEPT = 4


class Scorer(ShowModel):
    """A player who scored in an aired match."""

    player_id: str
    name: str
    goals: int = Field(ge=1)


class Result(ShowModel):
    """An aired match, as the desk will remember it."""

    fixture_key: str
    season: int
    matchday: int
    date: str
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    potm: str = ""
    potm_id: str = ""
    scorers: tuple[Scorer, ...] = ()

    def outcome(self) -> Pick:
        """Who won: ``home``, ``away`` or ``draw``."""
        if self.home_goals == self.away_goals:
            return "draw"
        return "home" if self.home_goals > self.away_goals else "away"


class Prediction(ShowModel):
    """A host's pick for a fixture that has not been played on air yet."""

    fixture_key: str
    host_id: str
    host_name: str
    pick: Pick


class GuestRequest(ShowModel):
    """A guest someone has asked for: they sit on the desk in the next interview slot."""

    person_id: str


class ShowBible(ShowModel):
    """The whole of the show's memory and position."""

    version: int = BIBLE_VERSION
    season: int = 1
    fixture_index: int = 0
    step: int = 0
    filler_index: int = 0
    table_due: bool = False
    segment_count: int = 0
    failures: int = 0
    date: str
    next_memory: int = 1
    results: tuple[Result, ...] = ()
    memories: tuple[MemoryRecord, ...] = ()
    predictions: tuple[Prediction, ...] = ()
    requests: tuple[GuestRequest, ...] = ()
    featured: Mapping[str, int] = Field(default_factory=dict)
    catchphrase_uses: Mapping[str, int] = Field(default_factory=dict)
    last_lines: tuple[str, ...] = ()

    @property
    def today(self) -> dt.date:
        """The show's in-world date: it moves on a week with every matchday."""
        return dt.date.fromisoformat(self.date)


def new_bible(start: dt.date) -> ShowBible:
    """A bible for a show that has never been on air, dated at the world's start."""
    return ShowBible(date=start.isoformat())
