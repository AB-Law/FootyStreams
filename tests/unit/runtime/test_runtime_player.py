from __future__ import annotations

import asyncio
from collections.abc import Sequence
from functools import cache

import pytest

from footystreams.events.broadcast import (
    BroadcastEvent,
    SegmentEndedEvent,
    SegmentKind,
    SegmentStartedEvent,
)
from footystreams.events.clock import period_elapsed_s
from footystreams.events.types import MatchEvent
from footystreams.runtime.bus import EventBus
from footystreams.runtime.clock import VirtualClock
from footystreams.runtime.config import Programme
from footystreams.runtime.cursor import NO_EVENT, Cursor, Phase
from footystreams.runtime.player import MatchPlayer, playing_offsets
from footystreams.runtime.programme import Block, BlockKind
from footystreams.runtime.sinks import InMemorySink
from footystreams.sim import SimConfig, default_tables, run_match
from tests.factories.sim_teams import make_demo_setup

pytestmark = pytest.mark.timeout(60)
PROGRAMME = Programme()


@cache
def _match() -> tuple[Block, tuple[MatchEvent, ...]]:
    """A really simulated match (about 1,400 events) and the block that would air it."""
    setup = make_demo_setup()
    result = run_match(setup, 7, SimConfig(), default_tables())
    block = Block(
        "2031-08-15:001:fix_demo:1",
        BlockKind.MATCH,
        str(setup.match_id),
        result.summary.duration_s + PROGRAMME.half_time_s,
    )
    return block, tuple(result.events)


class Harness:
    """A player over the virtual clock with a recording sink and cursor."""

    def __init__(self, *, cursor_every: int = 25, max_lag_s: float = 5.0) -> None:
        self.clock = VirtualClock()
        self.sink = InMemorySink(critical=True)
        self.saved: list[Cursor] = []
        self.on_event: list[object] = []
        self.bus = EventBus(queue_size=100_000, write_timeout_s=5.0)
        events = _match()[1]

        async def load(_: str) -> Sequence[MatchEvent]:
            return events

        async def persist(cursor: Cursor) -> None:
            self.saved.append(cursor)

        self.player = MatchPlayer(
            clock=self.clock,
            bus=self.bus,
            programme=PROGRAMME,
            load_events=load,
            persist=persist,
            cursor_every=cursor_every,
            max_lag_s=max_lag_s,
        )

    async def play(self, block: Block, resume_after: int = NO_EVENT) -> list[BroadcastEvent]:
        self.bus.add(self.sink)
        await self.player.play(block, resume_after)
        await self.bus.close()
        return self.sink.events


def _run(harness: Harness, block: Block, resume_after: int = NO_EVENT) -> list[BroadcastEvent]:
    return asyncio.run(harness.play(block, resume_after))


def _match_events(emitted: list[BroadcastEvent]) -> list[BroadcastEvent]:
    return [e for e in emitted if not isinstance(e, SegmentStartedEvent | SegmentEndedEvent)]


def test_playing_offsets__count_the_real_first_half_and_the_break() -> None:
    _, events = _match()
    offsets = playing_offsets(events, PROGRAMME.half_time_s)
    first_half = max(period_elapsed_s(e.clock) for e in events if e.clock.period == 1)
    second = next(o for o, e in zip(offsets, events, strict=True) if e.clock.period == 2)

    assert offsets == sorted(offsets)
    assert second == pytest.approx(first_half + PROGRAMME.half_time_s, abs=1)
    assert offsets[0] == 0


def test_play__airs_every_stored_event_unchanged_and_in_order() -> None:
    block, events = _match()

    emitted = _run(Harness(), block)

    assert _match_events(emitted) == list(events)


def test_play__the_match_ends_when_the_block_says_it_does_to_within_50_ms() -> None:
    block, _ = _match()
    harness = Harness()

    _run(harness, block)

    assert harness.clock.now() == pytest.approx(block.duration_s, abs=0.05)


def test_play__half_time_airs_between_the_halftime_event_and_the_second_half() -> None:
    block, _ = _match()
    emitted = _run(Harness(), block)

    kinds = [
        (e.type, getattr(e, "kind", None))
        for e in emitted
        if e.type in {"halftime", "kickoff"}
        or isinstance(e, SegmentStartedEvent | SegmentEndedEvent)
    ]
    halftime = next(i for i, k in enumerate(kinds) if k[0] == "halftime")

    assert kinds[halftime + 1] == ("segment_started", SegmentKind.HALF_TIME)
    assert kinds[halftime + 2] == ("segment_ended", SegmentKind.HALF_TIME)
    assert kinds[halftime + 3][0] == "kickoff"


def test_play__saves_the_cursor_at_the_start_every_n_events_and_at_the_end() -> None:
    block, events = _match()
    harness = Harness(cursor_every=100)

    _run(harness, block)

    assert harness.saved[0] == Cursor(block.id, Phase.STARTED, NO_EVENT)
    assert harness.saved[-1] == Cursor(block.id, Phase.DONE)
    midway = [c for c in harness.saved if c.phase is Phase.STARTED and c.after_seq >= 0]
    assert len(midway) == len(events) // 100
    assert [c.after_seq for c in midway] == sorted(c.after_seq for c in midway)


def test_play__resuming_airs_only_what_was_not_delivered_and_does_not_wait() -> None:
    block, events = _match()
    harness = Harness()
    last_aired = events[500].seq

    emitted = _run(harness, block, resume_after=last_aired)

    assert [e.id for e in _match_events(emitted)] == [e.id for e in events if e.seq > last_aired]
    already_played = playing_offsets(events, PROGRAMME.half_time_s)[501]
    assert harness.clock.now() == pytest.approx(block.duration_s - already_played, abs=0.05)


def test_play__a_cancelled_player_saves_where_it_had_got_to() -> None:
    block, _ = _match()
    harness = Harness(cursor_every=1000)

    async def scenario() -> None:
        harness.bus.add(harness.sink)
        task = asyncio.create_task(harness.player.play(block))
        while len(harness.sink.events) < 60:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await harness.bus.close()

    asyncio.run(scenario())

    seqs = [seq for e in harness.sink.events if (seq := getattr(e, "seq", None)) is not None]
    assert harness.saved[-1].phase is Phase.STARTED
    assert seqs[-1] <= harness.saved[-1].after_seq < len(_match()[1]) - 1


def test_play__a_clock_jump_does_not_make_the_overdue_events_burst_out() -> None:
    block, events = _match()
    harness = Harness(max_lag_s=5.0)
    offsets = playing_offsets(events, PROGRAMME.half_time_s)
    stamps: list[float] = []

    class Stamping(InMemorySink):
        async def write(self, event: BroadcastEvent) -> None:
            await super().write(event)
            stamps.append(harness.clock.now())
            if len(self.events) == 200:
                harness.clock.advance(3600.0)  # the machine slept for an hour

    harness.sink = Stamping(critical=True)
    emitted = _run(harness, block)
    after_jump = list(stamps[201:])

    assert len(_match_events(emitted)) == len(events)
    assert min(after_jump) >= stamps[200] - 1e-9
    spread = after_jump[-1] - after_jump[0]
    assert spread > 0.5 * (block.duration_s - offsets[200])


def test_play__a_segment_block_airs_started_waits_its_duration_then_ended() -> None:
    harness = Harness()
    segment = Block(
        "2031-09-06:001:fix_t00101:0", BlockKind.PRE_MATCH, "mch_1", 90.0, {"home": "A"}
    )

    emitted = _run(harness, segment)

    started, ended = emitted
    assert isinstance(started, SegmentStartedEvent)
    assert (started.id, started.duration_s, dict(started.facts)) == (
        "2031-09-06:001:fix_t00101:0:start",
        90.0,
        {"home": "A"},
    )
    assert isinstance(ended, SegmentEndedEvent)
    assert ended.id.endswith(":end")
    assert harness.clock.now() == 90.0
    assert harness.saved == [Cursor(segment.id, Phase.STARTED), Cursor(segment.id, Phase.DONE)]


def test_play__filler_airs_but_never_moves_the_cursor() -> None:
    harness = Harness()
    filler = Block("filler:000001", BlockKind.FILLER, "", 30.0, {"reason": "buffer_low"})

    emitted = _run(harness, filler)

    assert [e.type for e in emitted] == ["segment_started", "segment_ended"]
    assert harness.saved == []
