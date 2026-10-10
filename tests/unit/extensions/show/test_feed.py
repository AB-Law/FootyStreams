"""The feed the viewer plays: durations, the schedule, slotting segments in, the desk notes."""

from __future__ import annotations

from footystreams.extensions.show.feed import (
    OUTRO_S,
    ChannelIndex,
    aftermath,
    entry_of,
    insert_segments,
    line_duration_ms,
    schedule,
    scheduled_end,
    segment_id,
    stale_files,
    ticker_lines,
    with_cast,
    with_segment,
)
from footystreams.extensions.show.models import (
    MAX_LINE_MS,
    MIN_LINE_MS,
    Segment,
    SegmentKind,
    SpokenLine,
)
from footystreams.extensions.show.plan import Roster
from footystreams.extensions.show.producer import Producer
from tests.factories.show import EchoChat, FakeMatches, fresh_bible, newsroom


def segment(number: int, seconds: float = 60.0, air_at: float = 0.0) -> Segment:
    line = SpokenLine(
        speaker_id="med_a", speaker_name="Ann", text="A line.", duration_ms=MIN_LINE_MS
    )
    return Segment(
        id=segment_id(number),
        number=number,
        kind=SegmentKind.BANTER,
        title=f"Segment {number}",
        label="Desk chat",
        lines=(line,),
        duration_s=seconds,
        air_at=air_at,
    )


def feed(*segments: Segment, now: float = 0.0) -> ChannelIndex:
    index = ChannelIndex()
    for item in segments:
        index = with_segment(index, item, now, keep_s=10_000.0)
    return index


def spans(index: ChannelIndex) -> list[tuple[str, float, float]]:
    return [(e.id, e.air_at, e.air_at + e.duration_s) for e in index.segments]


def test_line_duration__scales_with_length_within_bounds() -> None:
    assert line_duration_ms("x" * 10) == MIN_LINE_MS
    assert line_duration_ms("x" * 150) > line_duration_ms("x" * 60)
    assert line_duration_ms("x" * 100_000) == MAX_LINE_MS


def test_schedule__segments_air_back_to_back() -> None:
    first = schedule(ChannelIndex(), segment(1, 60), now=1000.0, lead_s=15.0)
    assert first.air_at == 1015.0
    index = with_segment(ChannelIndex(), first, 1000.0)
    second = schedule(index, segment(2, 90), now=1001.0, lead_s=15.0)
    assert second.air_at == 1075.0
    assert scheduled_end(with_segment(index, second, 1001.0)) == 1165.0


def test_schedule__a_late_segment_airs_after_the_lead_not_in_the_past() -> None:
    index = feed(segment(1, 60, air_at=100.0))
    assert schedule(index, segment(2), now=5000.0, lead_s=15.0).air_at == 5015.0


def test_with_segment__keeps_what_aired_within_the_window_and_drops_the_rest() -> None:
    old, fresh = segment(1, 60, air_at=0.0), segment(2, 60, air_at=20_000.0)
    before = with_segment(ChannelIndex(), old, 0.0)
    kept = with_segment(before, fresh, 1000.0)
    assert [e.id for e in kept.segments] == [old.id, fresh.id]
    dropped = with_segment(before, fresh, 20_000.0, keep_s=3600.0)
    assert [e.id for e in dropped.segments] == [fresh.id]
    assert stale_files(before, dropped) == [f"{old.id}.json"]


def test_scheduled_end__is_zero_with_nothing_scheduled() -> None:
    assert scheduled_end(ChannelIndex()) == 0.0


def test_entry__lists_the_teaser_for_what_is_coming_and_the_real_title_for_later() -> None:
    recap = segment(3).model_copy(update={"title": "A 2-1 B", "teaser": "Match report: A v B"})
    entry = entry_of(recap)
    assert entry.title == "Match report: A v B"
    assert entry.headline == "A 2-1 B"
    assert entry_of(segment(4)).title == "Segment 4"


def test_insert__after_the_one_on_air_everything_still_to_come_moves_back() -> None:
    index = feed(
        segment(1, 100, air_at=1000.0), segment(2, 50, air_at=1100.0), segment(3, 50, air_at=1150.0)
    )
    guest = segment(9, 30)
    updated, scheduled = insert_segments(index, [guest], now=1040.0, lead_s=5.0, cut=False)
    assert scheduled[0].air_at == 1100.0
    assert spans(updated) == [
        ("seg_000001", 1000.0, 1100.0),
        ("seg_000009", 1100.0, 1130.0),
        ("seg_000002", 1130.0, 1180.0),
        ("seg_000003", 1180.0, 1230.0),
    ]


def test_insert__cutting_in_ends_the_one_on_air_and_starts_at_once() -> None:
    index = feed(segment(1, 100, air_at=1000.0), segment(2, 50, air_at=1100.0))
    flash, reaction = segment(8, 9), segment(9, 40)
    updated, scheduled = insert_segments(index, [flash, reaction], now=1040.0, lead_s=2.0, cut=True)
    assert [s.air_at for s in scheduled] == [1042.0, 1051.0]
    assert spans(updated) == [
        ("seg_000001", 1000.0, 1042.0),
        ("seg_000008", 1042.0, 1051.0),
        ("seg_000009", 1051.0, 1091.0),
        ("seg_000002", 1091.0, 1141.0),
    ]


def test_insert__into_a_gap_starts_after_the_lead_and_closes_ranks() -> None:
    index = feed(segment(1, 10, air_at=1000.0), segment(2, 50, air_at=1500.0))
    updated, scheduled = insert_segments(index, [segment(9, 20)], now=1200.0, lead_s=3.0, cut=False)
    assert scheduled[0].air_at == 1203.0
    assert spans(updated)[-1] == ("seg_000002", 1223.0, 1273.0)


def test_insert__never_touches_what_has_already_aired() -> None:
    index = feed(segment(1, 10, air_at=100.0), segment(2, 10, air_at=500.0))
    updated, _ = insert_segments(index, [segment(9, 20)], now=300.0, lead_s=2.0, cut=True)
    assert spans(updated)[0] == ("seg_000001", 100.0, 110.0)


def test_outro__is_part_of_the_airtime() -> None:
    maker = Producer(newsroom(), EchoChat(), FakeMatches())
    made = maker.produce(fresh_bible())
    lines_s = sum(line.duration_ms for line in made.segment.lines) / 1000
    assert made.segment.duration_s == lines_s + OUTRO_S


def test_ticker__results_leader_and_the_next_match() -> None:
    maker = Producer(newsroom(), EchoChat(), FakeMatches())
    bible = fresh_bible()
    assert ticker_lines(newsroom(), maker.roster, bible)[0].startswith("Next:")
    for _ in range(3):
        bible = maker.produce(bible).bible
    lines = ticker_lines(newsroom(), maker.roster, bible)
    assert lines[0].startswith("FT ")
    assert any("lead the table" in line for line in lines)
    assert lines[-1].startswith("Next:")


def test_ticker__a_season_that_is_over_has_no_next_match() -> None:
    roster = Roster.from_world(newsroom().world)
    bible = fresh_bible().model_copy(update={"fixture_index": len(roster.fixtures)})
    assert ticker_lines(newsroom(), roster, bible) == ("VPL News, 24 hours a day",)


def test_with_cast__lists_the_desk_in_seating_order() -> None:
    maker = Producer(newsroom(), EchoChat(), FakeMatches())
    index = with_cast(ChannelIndex(), maker.cast)
    assert [host.id for host in index.cast] == [member.id for member in maker.cast]


def test_segments__carry_the_ticker_and_memories_as_of_that_segment() -> None:
    maker = Producer(newsroom(), EchoChat(), FakeMatches())
    bible = fresh_bible()
    made = []
    for _ in range(3):
        step = maker.produce(bible)
        bible = step.bible
        made.append(step.segment)
    first, _, third = made
    assert not any(line.startswith("FT ") for line in first.ticker)
    assert third.ticker[0].startswith("FT ")
    assert len(third.memories) >= len(first.memories)
    assert len({note.text for note in third.memories}) == len(third.memories)
    assert aftermath(newsroom(), maker.roster, bible, maker.cast).ticker == third.ticker


def test_recaps__are_listed_by_fixture_never_by_score() -> None:
    maker = Producer(newsroom(), EchoChat(), FakeMatches())
    bible = fresh_bible()
    for _ in range(2):
        bible = maker.produce(bible).bible
    recap = maker.produce(bible).segment
    assert recap.kind is SegmentKind.RECAP
    entry = entry_of(recap)
    assert entry.title.startswith("Match report: ")
    assert not any(char.isdigit() for char in entry.title)
    assert recap.title == entry.headline != entry.title
