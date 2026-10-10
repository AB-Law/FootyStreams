"""The feed the viewer plays: segments on a wall-clock schedule, kept for hours for replay.

Segments are scheduled back to back from the moment the last one ends, so the channel has one
timeline that every viewer joins in the middle of. If the producer falls behind, the next segment
airs as soon as it is ready and the viewer shows a stand-by scene for the gap. Segments asked for
(a guest, breaking news) are slotted in: after the one on air, or cutting it off, with everything
still to come moved back to make room.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.ledger import scoreline, season_results, table
from footystreams.extensions.show.memory import retrieve, text_of
from footystreams.extensions.show.models import (
    MAX_LINE_MS,
    MIN_LINE_MS,
    CastMember,
    MemoryNote,
    Segment,
    ShowModel,
    SpokenLine,
)
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.plan import Plan, Roster
from footystreams.extensions.show.reply import Reply
from footystreams.extensions.show.segment_brief import SegmentBrief

CHARS_PER_SECOND = 15
HOLD_MS = 1_400
OUTRO_S = 4.0
FEED_VERSION = 2
TICKER_RESULTS = 4
NOTES_PER_HOST = 4
KEEP_PAST_S = 4 * 3600.0
MIN_CUT_S = 0.5


def line_duration_ms(text: str) -> int:
    """How long a line holds the screen: time to say it at speaking pace plus a beat."""
    return min(max(round(len(text) / CHARS_PER_SECOND * 1000) + HOLD_MS, MIN_LINE_MS), MAX_LINE_MS)


def segment_id(number: int) -> str:
    """The id of the ``number``th segment, which is also its file stem."""
    return f"seg_{number:06d}"


def build_segment(
    plan: Plan, brief: SegmentBrief, cast: Sequence[CastMember], reply: Reply
) -> Segment:
    """A finished segment from a checked reply; ``cast`` is everyone who may speak."""
    names = {member.id: member.name for member in cast}
    lines = tuple(
        SpokenLine(
            speaker_id=line.speaker_id,
            speaker_name=names[line.speaker_id],
            text=line.text,
            duration_ms=line_duration_ms(line.text),
            uses=line.uses,
        )
        for line in reply.lines
    )
    return Segment(
        id=segment_id(plan.number),
        number=plan.number,
        kind=plan.kind,
        title=brief.title,
        teaser=brief.teaser,
        label=brief.label,
        lines=lines,
        screen=brief.screen,
        guest=brief.guest,
        alert=brief.alert,
        duration_s=sum(line.duration_ms for line in lines) / 1000 + OUTRO_S,
    )


class IndexEntry(ShowModel):
    """One scheduled segment, as listed in the feed.

    ``title`` is the spoiler-free teaser used for what is still to come; ``headline`` is the real
    title, for the list of what has already aired.
    """

    id: str
    file: str
    kind: str
    title: str
    headline: str
    label: str
    guest: str = ""
    air_at: float
    duration_s: float


class HostRef(ShowModel):
    """A host at the desk, in seating order."""

    id: str
    name: str


class ChannelIndex(ShowModel):
    """The whole feed: the desk and the schedule, past and to come."""

    version: int = FEED_VERSION
    channel: str = "VPL News"
    generated_at: float = 0.0
    cast: tuple[HostRef, ...] = ()
    segments: tuple[IndexEntry, ...] = ()


def entry_of(segment: Segment) -> IndexEntry:
    """The feed's line for a segment."""
    return IndexEntry(
        id=segment.id,
        file=f"{segment.id}.json",
        kind=segment.kind.value,
        title=segment.teaser or segment.title,
        headline=segment.title,
        label=segment.label,
        guest=segment.guest.name if segment.guest else "",
        air_at=segment.air_at,
        duration_s=segment.duration_s,
    )


def scheduled_end(index: ChannelIndex) -> float:
    """When the last scheduled segment ends, or 0 if nothing is scheduled."""
    return max((entry.air_at + entry.duration_s for entry in index.segments), default=0.0)


def schedule(index: ChannelIndex, segment: Segment, now: float, lead_s: float) -> Segment:
    """``segment`` with its air time: right after the last one, or ``lead_s`` from now if behind."""
    return segment.model_copy(update={"air_at": max(scheduled_end(index), now + lead_s)})


def with_segment(
    index: ChannelIndex, segment: Segment, now: float, keep_s: float = KEEP_PAST_S
) -> ChannelIndex:
    """The feed with ``segment`` added; segments that aired more than ``keep_s`` ago are dropped."""
    current = tuple(e for e in index.segments if e.air_at + e.duration_s > now - keep_s)
    return index.model_copy(update={"segments": (*current, entry_of(segment)), "generated_at": now})


def insert_segments(
    index: ChannelIndex, segments: Sequence[Segment], now: float, lead_s: float, *, cut: bool
) -> tuple[ChannelIndex, list[Segment]]:
    """Slot ``segments`` in ahead of everything still to come.

    They start after the segment on air, or if ``cut`` right away (``lead_s`` from now), ending the
    one on air there. Segments that had not started yet are moved back, in order, to follow them.
    Returns the new feed and the segments with their air times.
    """
    live = next((e for e in index.segments if e.air_at <= now < e.air_at + e.duration_s), None)
    start = live.air_at + live.duration_s if live is not None and not cut else now + lead_s
    begun = [
        e.model_copy(update={"duration_s": max(start - e.air_at, MIN_CUT_S)})
        if cut and live is not None and e.id == live.id
        else e
        for e in index.segments
        if e.air_at <= now
    ]
    later = [e for e in index.segments if e.air_at > now]
    scheduled: list[Segment] = []
    cursor = start
    for segment in segments:
        scheduled.append(segment.model_copy(update={"air_at": cursor}))
        cursor += segment.duration_s
    moved: list[IndexEntry] = []
    for entry in later:
        moved.append(entry.model_copy(update={"air_at": cursor}))
        cursor += entry.duration_s
    entries = (*begun, *(entry_of(s) for s in scheduled), *moved)
    return index.model_copy(update={"segments": entries, "generated_at": now}), scheduled


def stale_files(before: ChannelIndex, after: ChannelIndex) -> list[str]:
    """The segment files that dropped out of the feed and can be deleted."""
    kept = {entry.file for entry in after.segments}
    return [entry.file for entry in before.segments if entry.file not in kept]


def ticker_lines(room: Newsroom, roster: Roster, bible: ShowBible) -> tuple[str, ...]:
    """Headlines for the ticker: the latest results, the leaders and the next match."""
    results = season_results(bible.results, bible.season)
    lines = [f"FT {scoreline(result)}" for result in reversed(results[-TICKER_RESULTS:])]
    if results:
        leader = table(results, room.club_names)[0]
        lines.append(f"{leader.name} lead the table on {leader.points} points")
    if bible.fixture_index < len(roster.fixtures):
        fixture = roster.fixtures[bible.fixture_index]
        lines.append(
            f"Next: {room.club_names[fixture.home_id]} v {room.club_names[fixture.away_id]}"
        )
    return tuple(lines) or ("VPL News, 24 hours a day",)


def memory_notes(bible: ShowBible, cast: Sequence[CastMember]) -> tuple[MemoryNote, ...]:
    """What each host has most in mind right now."""
    seen: set[str] = set()
    notes: list[MemoryNote] = []
    for host in cast:
        for memory in retrieve(bible.memories, host.id, frozenset(), bible.today, NOTES_PER_HOST):
            if memory.id not in seen:
                seen.add(memory.id)
                notes.append(MemoryNote(host=host.name, kind=memory.kind, text=text_of(memory)))
    return tuple(notes)


@dataclass(frozen=True, slots=True)
class Aftermath:
    """The ticker and what the hosts remember once a segment has aired."""

    ticker: tuple[str, ...]
    memories: tuple[MemoryNote, ...]


def aftermath(
    room: Newsroom, roster: Roster, bible: ShowBible, cast: Sequence[CastMember]
) -> Aftermath:
    """The ticker and memory notes for the desk as it stands in ``bible``."""
    return Aftermath(ticker_lines(room, roster, bible), memory_notes(bible, cast))


def with_aftermath(segment: Segment, after: Aftermath) -> Segment:
    """``segment`` carrying the desk as it stands once it has aired."""
    return segment.model_copy(update={"ticker": after.ticker, "memories": after.memories})


def with_cast(index: ChannelIndex, cast: Sequence[CastMember]) -> ChannelIndex:
    """The feed listing ``cast`` at the desk, in seating order."""
    return index.model_copy(
        update={"cast": tuple(HostRef(id=member.id, name=member.name) for member in cast)}
    )
