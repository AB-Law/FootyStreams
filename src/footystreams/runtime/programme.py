"""The programme: the world's played matchdays laid out as timed blocks on the one channel.

Everything here is a pure function of the database and the placeholder durations, so a restarted
engine rebuilds exactly the same list and the cursor can say "after block X". For each played
fixture, in kickoff order, there is a ``pre_match`` segment, the ``match`` itself and a
``post_match`` segment; when every fixture of a matchday has been played the matchday ends with a
``matchday_magazine`` (the results, the table leader and the day's news). A match whose log failed
verification is aired as ``filler`` instead, so the stream never carries it.

Block ids sort in broadcast order: ``date:matchday:fixture:ordinal`` (the magazine uses ``~`` for
the fixture so it follows the matches, and ordinal 9).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.mood import ModifierVisibility, WorldEvent
from footystreams.events.broadcast import Fact, SegmentKind
from footystreams.persistence.ports import Repositories
from footystreams.runtime.config import Programme
from footystreams.runtime.cursor import Cursor, Phase

PLAYED = FixtureStatus.PLAYED.value
DEFAULT_MATCH_S = 5640.0  # two halves and stoppage, used only when a summary is missing
PRE, MATCH, POST, MAGAZINE = 0, 1, 2, 9
MAGAZINE_FIXTURE = "~"  # sorts after every fixture id


class BlockKind(StrEnum):
    """What a block is: a match or one of the segments."""

    PRE_MATCH = "pre_match"
    MATCH = "match"
    POST_MATCH = "post_match"
    MATCHDAY_MAGAZINE = "matchday_magazine"
    FILLER = "filler"

    @property
    def segment(self) -> SegmentKind:
        """The segment kind of a non-match block."""
        return SegmentKind(self.value)


@dataclass(frozen=True, slots=True)
class Block:
    """One timed block: its id, kind, subject (a match id for a match), length and facts."""

    id: str
    kind: BlockKind
    subject_ref: str
    duration_s: float
    facts: Mapping[str, Fact] = field(default_factory=dict)


def block_id(fixture: Fixture, ordinal: int) -> str:
    """The sortable id of a fixture's block: ``date:matchday:fixture:ordinal``."""
    return f"{fixture.date.isoformat()}:{fixture.matchday:03d}:{fixture.id}:{ordinal}"


def magazine_id(fixture: Fixture) -> str:
    """The id of the magazine that closes the matchday of ``fixture``."""
    return f"{fixture.date.isoformat()}:{fixture.matchday:03d}:{MAGAZINE_FIXTURE}:{MAGAZINE}"


def filler_id(number: int) -> str:
    """The id of the ``number``-th filler block of a run (fillers never move the cursor)."""
    return f"filler:{number:06d}"


def _names(repositories: Repositories, fixture: Fixture) -> dict[str, Fact]:
    home = repositories.clubs.require(fixture.home_club_id)
    away = repositories.clubs.require(fixture.away_club_id)
    return {
        "home": home.name,
        "away": away.name,
        "home_code": home.short_code,
        "away_code": away.short_code,
        "derby": fixture.is_derby,
        "matchday": fixture.matchday,
        "date": fixture.date.isoformat(),
    }


def _match_seconds(repositories: Repositories, fixture: Fixture, programme: Programme) -> float:
    record = repositories.summaries.get(str(fixture.match_id))
    played = float(record.summary.duration_s) if record is not None else DEFAULT_MATCH_S
    return played + programme.half_time_s


def _match_blocks(
    repositories: Repositories,
    fixture: Fixture,
    programme: Programme,
    quarantined: Collection[str],
) -> list[Block]:
    facts = _names(repositories, fixture)
    match_id = str(fixture.match_id)
    if match_id in quarantined:
        withheld = {**facts, "reason": "quarantined", "match_id": match_id}
        return [Block(block_id(fixture, MATCH), BlockKind.FILLER, "", programme.filler_s, withheld)]
    match = repositories.matches.get(match_id)
    result: dict[str, Fact] = (
        {"home_goals": match.home_goals or 0, "away_goals": match.away_goals or 0}
        if match is not None
        else {}
    )
    return [
        Block(block_id(fixture, PRE), BlockKind.PRE_MATCH, match_id, programme.pre_match_s, facts),
        Block(
            block_id(fixture, MATCH),
            BlockKind.MATCH,
            match_id,
            _match_seconds(repositories, fixture, programme),
            facts,
        ),
        Block(
            block_id(fixture, POST),
            BlockKind.POST_MATCH,
            match_id,
            programme.post_match_s,
            {**facts, **result},
        ),
    ]


def news_of(repositories: Repositories, date: dt.date) -> list[WorldEvent]:
    """The public world events of ``date``, in id order (what the channel may talk about)."""
    events = repositories.world_events.find({"date": date})
    return sorted(
        (e for e in events if e.visibility is ModifierVisibility.PUBLIC), key=lambda e: e.id
    )


def _magazine(repositories: Repositories, day: Sequence[Fixture], programme: Programme) -> Block:
    last = day[-1]
    goals = 0
    for fixture in day:
        match = repositories.matches.get(str(fixture.match_id))
        if match is not None:
            goals += (match.home_goals or 0) + (match.away_goals or 0)
    facts: dict[str, Fact] = {
        "matchday": last.matchday,
        "date": last.date.isoformat(),
        "matches": len(day),
        "goals": goals,
        "news": len(news_of(repositories, last.date)),
    }
    return Block(magazine_id(last), BlockKind.MATCHDAY_MAGAZINE, "", programme.magazine_s, facts)


def _matchdays(repositories: Repositories) -> list[list[Fixture]]:
    """Played fixtures grouped by (season, matchday), in kickoff order; only complete matchdays."""
    played = repositories.fixtures.find({"status": PLAYED})
    grouped: dict[tuple[str, int], list[Fixture]] = defaultdict(list)
    for fixture in played:
        grouped[(fixture.season_id, fixture.matchday)].append(fixture)
    days = [sorted(day, key=lambda f: (f.date, f.id)) for day in grouped.values()]
    return sorted(days, key=lambda day: (day[0].date, day[0].matchday, day[0].id))


def _complete(repositories: Repositories, day: Sequence[Fixture]) -> bool:
    first = day[0]
    waiting = repositories.fixtures.count(
        {"season_id": first.season_id, "matchday": first.matchday, "status": "scheduled"}
    )
    return waiting == 0


def build_programme(
    repositories: Repositories, programme: Programme, quarantined: Collection[str] = ()
) -> list[Block]:
    """Every block of every played matchday, in broadcast order."""
    blocks: list[Block] = []
    for day in _matchdays(repositories):
        for fixture in day:
            blocks.extend(_match_blocks(repositories, fixture, programme, quarantined))
        if _complete(repositories, day):
            blocks.append(_magazine(repositories, day, programme))
    return blocks


def after(blocks: Sequence[Block], cursor: Cursor | None) -> list[Block]:
    """The blocks still to air given the cursor (the one it names too, if it was mid-block)."""
    if cursor is None:
        return list(blocks)
    if cursor.phase is Phase.STARTED:
        return [block for block in blocks if block.id >= cursor.block]
    return [block for block in blocks if block.id > cursor.block]
