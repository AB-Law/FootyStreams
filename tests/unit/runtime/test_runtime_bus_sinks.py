from __future__ import annotations

import asyncio
import io
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from footystreams.events.broadcast import BroadcastEvent, EngineMarker, MarkerKind, from_line
from footystreams.runtime.bus import EventBus
from footystreams.runtime.sinks import (
    InMemorySink,
    NdjsonFileSink,
    NdjsonStreamSink,
    build_sinks,
)

pytestmark = pytest.mark.timeout(30)


def _event(number: int) -> BroadcastEvent:
    return EngineMarker(id=f"marker:{number:03d}", marker=MarkerKind.START)


def _ids(events: list[BroadcastEvent]) -> list[str]:
    return [event.id for event in events]


async def _no_wait(_: float) -> None:
    return None


def _bus(**changes: Any) -> EventBus:
    settings: dict[str, Any] = {"queue_size": 100, "write_timeout_s": 1.0, "sleep": _no_wait}
    return EventBus(**{**settings, **changes})


class RecordingSink:
    """Accepts everything; optionally holds each write until a gate opens or fails on demand."""

    def __init__(
        self,
        name: str,
        *,
        critical: bool = False,
        delay_s: float = 0.0,
        fail_first: int = 0,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.name = name
        self.critical = critical
        self.written: list[BroadcastEvent] = []
        self.closed = 0
        self._delay_s = delay_s
        self._fail_first = fail_first
        self._gate = gate
        self.attempts = 0

    async def write(self, event: BroadcastEvent) -> None:
        self.attempts += 1
        if self._gate is not None:
            await self._gate.wait()
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        if self.attempts <= self._fail_first:
            msg = "sink is down"
            raise ConnectionError(msg)
        self.written.append(event)

    async def close(self) -> None:
        self.closed += 1


def _run(coroutine: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coroutine)


def test_bus__every_sink_gets_every_event_in_order() -> None:
    async def scenario() -> None:
        bus, first, second = _bus(), RecordingSink("a"), RecordingSink("b")
        bus.add(first)
        bus.add(second)
        for number in range(30):
            await bus.emit(_event(number))
        await bus.close()

        expected = [f"marker:{n:03d}" for n in range(30)]
        assert _ids(first.written) == _ids(second.written) == expected
        assert (first.closed, second.closed) == (1, 1)
        assert bus.stats()["a"].delivered == 30

    _run(scenario())


def test_bus__a_slow_sink_does_not_hold_up_a_fast_one() -> None:
    async def scenario() -> None:
        bus, slow, fast = _bus(), RecordingSink("slow", delay_s=0.05), RecordingSink("fast")
        bus.add(slow)
        bus.add(fast)
        for number in range(10):
            await bus.emit(_event(number))
        await asyncio.sleep(0.03)

        assert len(fast.written) == 10
        assert len(slow.written) < 10
        await bus.close()
        assert len(slow.written) == 10

    _run(scenario())


def test_bus__a_best_effort_sink_that_fails_drops_those_events_and_recovers() -> None:
    async def scenario() -> None:
        bus, flaky, steady = _bus(), RecordingSink("flaky", fail_first=2), RecordingSink("steady")
        bus.add(flaky)
        bus.add(steady)
        for number in range(5):
            await bus.emit(_event(number))
        await bus.close()

        stats = bus.stats()["flaky"]
        assert (stats.delivered, stats.dropped, stats.failures) == (3, 2, 2)
        assert len(steady.written) == 5

    _run(scenario())


def test_bus__a_full_best_effort_queue_drops_the_oldest_events() -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        bus, held = _bus(queue_size=3), RecordingSink("viewer", gate=gate)
        bus.add(held)
        await bus.emit(_event(0))
        await asyncio.sleep(0.01)  # the worker takes event 0 and waits at the gate
        for number in range(1, 10):
            await bus.emit(_event(number))
        gate.set()
        await bus.close()

        assert _ids(held.written) == ["marker:000", "marker:007", "marker:008", "marker:009"]
        assert bus.stats()["viewer"].dropped == 6

    _run(scenario())


def test_bus__a_critical_sink_retries_a_failing_write_and_keeps_the_event() -> None:
    async def scenario() -> None:
        bus, archive = _bus(), RecordingSink("archive", critical=True, fail_first=2)
        bus.add(archive)
        await bus.emit(_event(1))
        await bus.close()

        stats = bus.stats()["archive"]
        assert (stats.delivered, stats.failures, stats.lost) == (1, 2, 0)
        assert _ids(archive.written) == ["marker:001"]

    _run(scenario())


def test_bus__a_critical_sink_that_never_recovers_loses_the_event_and_says_so() -> None:
    async def scenario() -> None:
        bus, archive = _bus(), RecordingSink("archive", critical=True, fail_first=99)
        bus.add(archive)
        await bus.emit(_event(1))
        await bus.close()

        stats = bus.stats()["archive"]
        assert (stats.delivered, stats.lost, stats.failures) == (0, 1, 3)

    _run(scenario())


def test_bus__the_producer_waits_for_a_critical_sink_only_for_a_bounded_time() -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        bus = _bus(queue_size=1, backpressure_s=0.05)
        archive = RecordingSink("archive", critical=True, gate=gate)
        bus.add(archive)
        await bus.emit(_event(0))
        await asyncio.sleep(0.01)  # in flight, blocked
        await bus.emit(_event(1))  # fills the queue
        loop = asyncio.get_running_loop()
        started = loop.time()

        await bus.emit(_event(2))  # no room: waits out the window, then counts it lost

        assert loop.time() - started < 1.0
        assert bus.stats()["archive"].lost == 1
        gate.set()
        await bus.close()
        assert _ids(archive.written) == ["marker:000", "marker:001"]

    _run(scenario())


def test_bus__a_write_that_takes_too_long_counts_as_a_failure() -> None:
    async def scenario() -> None:
        bus = _bus(write_timeout_s=0.02)
        stuck = RecordingSink("stuck", delay_s=1.0)
        bus.add(stuck)
        await bus.emit(_event(1))
        await bus.close()

        stats = bus.stats()["stuck"]
        assert (stats.delivered, stats.dropped, stats.failures) == (0, 1, 1)

    _run(scenario())


def test_bus__flush_waits_for_everything_emitted() -> None:
    async def scenario() -> None:
        bus, sink = _bus(), RecordingSink("a", delay_s=0.01)
        bus.add(sink)
        for number in range(5):
            await bus.emit(_event(number))

        await bus.flush()

        assert len(sink.written) == 5
        await bus.close()

    _run(scenario())


def test_in_memory_sink__keeps_events_in_order() -> None:
    async def scenario() -> None:
        sink = InMemorySink()
        await sink.write(_event(1))
        await sink.write(_event(2))

        assert _ids(sink.events) == ["marker:001", "marker:002"]

    _run(scenario())


def test_stream_sink__writes_one_parseable_line_per_event() -> None:
    async def scenario() -> None:
        stream = io.StringIO()
        sink = NdjsonStreamSink(stream)
        await sink.write(_event(1))
        await sink.write(_event(2))
        await sink.close()

        lines = stream.getvalue().splitlines()
        assert [from_line(line).id for line in lines] == ["marker:001", "marker:002"]

    _run(scenario())


def test_file_sink__appends_lines_and_creates_missing_folders(tmp_path: Path) -> None:
    async def scenario() -> None:
        path = tmp_path / "archive" / "broadcast.ndjson"
        sink = NdjsonFileSink(path)
        await sink.write(_event(1))
        await sink.close()

        assert from_line(path.read_text(encoding="utf-8").strip()).id == "marker:001"
        assert sink.critical is True

    _run(scenario())


def test_file_sink__rotates_to_a_numbered_file_past_the_size_limit(tmp_path: Path) -> None:
    async def scenario() -> None:
        path = tmp_path / "broadcast.ndjson"
        sink = NdjsonFileSink(path, rotate_bytes=200)
        for number in range(8):
            await sink.write(_event(number))
        await sink.close()

        parts = sorted(tmp_path.glob("broadcast.ndjson*"))
        lines = [line for part in parts for line in part.read_text(encoding="utf-8").splitlines()]
        assert len(parts) > 1
        assert [from_line(line).id for line in lines] == [f"marker:{n:03d}" for n in range(8)]

    _run(scenario())


def test_build_sinks__reads_the_specs_and_rejects_unknown_ones(tmp_path: Path) -> None:
    sinks = build_sinks(("memory", f"ndjson:file:{tmp_path / 'a.ndjson'}", "ndjson:stdout"))

    assert [type(sink).__name__ for sink in sinks] == [
        "InMemorySink",
        "NdjsonFileSink",
        "NdjsonStreamSink",
    ]
    with pytest.raises(ValueError, match="unknown sink"):
        build_sinks(("carrier-pigeon",))
