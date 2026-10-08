"""``EventBus``: fan an event out to every sink without letting any sink slow the channel down.

Each sink has its own bounded queue and its own worker task, so a slow, failing or disconnected
sink only ever hurts itself. Two kinds of sink:

* **best effort** (a viewer, a debug tap): when its queue is full the *oldest* event is dropped and
  counted; a write that raises or times out is dropped and counted;
* **critical** (the archive): the producer waits for room, but only for a bounded window; a write
  that fails is retried with backoff. If either gives up the event is counted as *lost* and the
  health report says so, instead of the stream stalling.

``flush`` waits for the queues to empty and ``close`` flushes, stops the workers and closes the
sinks, so a graceful shutdown delivers everything already emitted.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from footystreams.events.broadcast import BroadcastEvent

LOGGER = logging.getLogger(__name__)
CRITICAL_ATTEMPTS = 3
BACKOFF_START_S = 0.05

Sleep = Callable[[float], Awaitable[None]]


class EventSink(Protocol):
    """A consumer of the broadcast: write events in order; ``close`` releases resources."""

    name: str
    critical: bool

    async def write(self, event: BroadcastEvent) -> None:
        """Deliver one event; may raise, or take longer than the bus allows."""

    async def close(self) -> None:
        """Release resources; called once, after the last write."""


@dataclass(slots=True)
class SinkStats:
    """What happened to the events offered to one sink."""

    delivered: int = 0
    dropped: int = 0  # best-effort sinks: queue overflow or a failed write
    lost: int = 0  # critical sinks: the producer's wait ran out or the retries did
    failures: int = 0  # individual write attempts that raised or timed out
    depth: int = 0  # events queued right now


@dataclass(slots=True)
class _Channel:
    sink: EventSink
    queue: asyncio.Queue[BroadcastEvent]
    stats: SinkStats = field(default_factory=SinkStats)
    worker: asyncio.Task[None] | None = None


class EventBus:
    """Fan-out to sinks with per-sink bounded queues (see the module docstring)."""

    def __init__(
        self,
        *,
        queue_size: int,
        write_timeout_s: float,
        backpressure_s: float = 1.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        """Create a bus; ``sleep`` is injectable so tests do not wait out the retry backoff."""
        self._queue_size = queue_size
        self._write_timeout_s = write_timeout_s
        self._backpressure_s = backpressure_s
        self._sleep = sleep
        self._channels: list[_Channel] = []

    def add(self, sink: EventSink) -> None:
        """Attach a sink and start its worker; call from inside the running event loop."""
        channel = _Channel(sink, asyncio.Queue(self._queue_size))
        channel.worker = asyncio.create_task(self._run(channel), name=f"sink:{sink.name}")
        self._channels.append(channel)

    async def emit(self, event: BroadcastEvent) -> None:
        """Offer ``event`` to every sink; waits only for critical sinks, and only a bounded time."""
        for channel in self._channels:
            if channel.sink.critical:
                await self._offer_critical(channel, event)
            else:
                self._offer_best_effort(channel, event)

    def _offer_best_effort(self, channel: _Channel, event: BroadcastEvent) -> None:
        if channel.queue.full():
            channel.queue.get_nowait()
            channel.queue.task_done()
            channel.stats.dropped += 1
        channel.queue.put_nowait(event)

    async def _offer_critical(self, channel: _Channel, event: BroadcastEvent) -> None:
        try:
            await asyncio.wait_for(channel.queue.put(event), self._backpressure_s)
        except TimeoutError:
            channel.stats.lost += 1
            LOGGER.warning(
                "sink %s: queue full for %.1fs, event lost", channel.sink.name, self._backpressure_s
            )

    async def _run(self, channel: _Channel) -> None:
        attempts = CRITICAL_ATTEMPTS if channel.sink.critical else 1
        while True:
            event = await channel.queue.get()
            try:
                if await self._deliver(channel, event, attempts):
                    channel.stats.delivered += 1
                elif channel.sink.critical:
                    channel.stats.lost += 1
                else:
                    channel.stats.dropped += 1
            finally:
                channel.queue.task_done()

    async def _deliver(self, channel: _Channel, event: BroadcastEvent, attempts: int) -> bool:
        backoff = BACKOFF_START_S
        for attempt in range(1, attempts + 1):
            try:
                await asyncio.wait_for(channel.sink.write(event), self._write_timeout_s)
            except Exception as error:  # noqa: BLE001 - the isolation boundary: a sink may raise anything
                channel.stats.failures += 1
                LOGGER.warning(
                    "sink %s: write failed (attempt %d): %r", channel.sink.name, attempt, error
                )
                if attempt < attempts:
                    await self._sleep(backoff)
                    backoff *= 2
            else:
                return True
        return False

    async def flush(self) -> None:
        """Wait until every queued event has been delivered, dropped or lost."""
        await asyncio.gather(*(channel.queue.join() for channel in self._channels))

    async def close(self) -> None:
        """Flush, stop the workers and close every sink."""
        await self.flush()
        for channel in self._channels:
            if channel.worker is not None:
                channel.worker.cancel()
        await asyncio.gather(
            *(c.worker for c in self._channels if c.worker), return_exceptions=True
        )
        for channel in self._channels:
            await channel.sink.close()

    def stats(self) -> Mapping[str, SinkStats]:
        """A snapshot of every sink's counters, by sink name."""
        for channel in self._channels:
            channel.stats.depth = channel.queue.qsize()
        return {channel.sink.name: channel.stats for channel in self._channels}
