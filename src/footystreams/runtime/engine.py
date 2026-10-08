"""``Engine``: the long-running service that keeps the channel on air.

It takes the single-instance lock, announces itself, and runs two supervised tasks: the
``SimulationBuffer`` keeps the world matchdays ahead of the broadcast, and the broadcast loop airs
whatever the programme says is next, resuming from the stored cursor. When the buffer cannot supply
the next block in time the broadcast airs filler, so the stream never stalls. The process may be
killed at any instant: on restart it reloads the cursor and carries on, preceded by a ``resume``
marker, and consumers drop the few repeated ids by ``(match_id, seq)``.

A graceful stop (``request_stop``, wired to SIGINT/SIGTERM by the command) cancels the tasks, which
persist the cursor, announces ``stop``, flushes every sink and releases the lock. A finite run
(``max_seasons`` / ``until_date``) ends by itself once the broadcast has drained the programme.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Executor
from dataclasses import dataclass
from enum import StrEnum

from footystreams.events.broadcast import EngineMarker, MarkerKind
from footystreams.events.types import MatchEvent
from footystreams.persistence.ports import UnitOfWorkFactory
from footystreams.persistence.records import MetaEntry
from footystreams.runtime.buffer import Limits, SimulationBuffer, Step
from footystreams.runtime.bus import EventBus, EventSink
from footystreams.runtime.clock import Clock
from footystreams.runtime.config import EngineConfig
from footystreams.runtime.cursor import NO_EVENT, Cursor, Phase, advance_cursor, load_cursor
from footystreams.runtime.health import HealthReporter, Status
from footystreams.runtime.lock import InstanceLock
from footystreams.runtime.player import MatchPlayer
from footystreams.runtime.programme import (
    Block,
    BlockKind,
    after,
    build_programme,
    filler_id,
)
from footystreams.runtime.supervisor import Outcome, Sleep, Supervisor

LOGGER = logging.getLogger(__name__)
RUNS_KEY = "engine_runs"


class ExitReason(StrEnum):
    """Why ``run`` returned."""

    FINISHED = "finished"  # a finite run played everything it was asked to
    STOPPED = "stopped"  # a graceful stop was requested
    FAILED = "failed"  # the broadcast itself could not be kept running


@dataclass(frozen=True, slots=True)
class EngineParts:
    """The collaborators the composition root supplies."""

    factory: UnitOfWorkFactory
    step: Step
    sinks: Sequence[EventSink]
    clock: Clock
    executor: Executor | None = None
    sleep: Sleep = asyncio.sleep
    wall: Callable[[], float] = time.time


class Engine:
    """Runs the channel (see the module docstring)."""

    def __init__(self, config: EngineConfig, parts: EngineParts) -> None:
        """Create an engine; nothing starts until ``run``."""
        self._config = config
        self._parts = parts
        self._health = HealthReporter(config.health_path, parts.wall)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._buffer: SimulationBuffer | None = None
        self._player: MatchPlayer | None = None
        self._bus: EventBus | None = None
        self._fillers = 0
        self._save_lock = threading.Lock()  # cursor saves in threads must not overlap

    # ------------------------------------------------------------------------------------ run

    def request_stop(self) -> None:
        """Ask the engine to stop gracefully; safe from a signal handler or another thread."""
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)

    async def run(self) -> ExitReason:
        """Hold the lock and keep the channel on air until finished, stopped or failed."""
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        lock = InstanceLock(self._config.lock_path)
        lock.acquire(grace_s=self._config.lock_grace_s)
        try:
            return await self._run_locked()
        finally:
            lock.release()

    async def _run_locked(self) -> ExitReason:
        config, health = self._config, self._health
        cursor = await asyncio.to_thread(self._read_cursor)
        run_number = await asyncio.to_thread(self._next_run)
        health.update(status=Status.STARTING)
        bus = self._bus = EventBus(
            queue_size=config.sink_queue,
            write_timeout_s=config.sink_timeout_s,
            sleep=self._parts.sleep,
        )
        for sink in self._parts.sinks:
            bus.add(sink)
        buffer = self._buffer = SimulationBuffer(
            step=self._parts.step,
            executor=self._parts.executor,
            factory=self._parts.factory,
            programme=config.programme,
            limits=Limits(
                depth=config.buffer_matchdays,
                max_seasons=config.max_seasons,
                until_date=config.until_date,
                frozen=config.safe_mode,
            ),
        )
        await asyncio.to_thread(buffer.prime, cursor)
        self._player = self._make_player(bus)
        await self._announce(run_number, cursor)
        health.update(status=Status.DEGRADED if config.safe_mode else Status.RUNNING)
        reason = await self._supervise(buffer)
        await self._announce_stop(run_number, reason)
        health.update(status=Status.STOPPING)
        await bus.close()
        health.update(status=Status.STOPPED, sinks=self._sink_stats(bus))
        return reason

    async def _supervise(self, buffer: SimulationBuffer) -> ExitReason:
        assert self._stop is not None  # noqa: S101 - set by run()
        supervisor = Supervisor(sleep=self._parts.sleep)

        async def feed() -> None:
            if await supervisor.supervise("buffer", buffer.run) is Outcome.CIRCUIT_OPEN:
                buffer.failed = True
                self._health.update(status=Status.DEGRADED, notes=("buffer circuit open",))

        feeding = asyncio.create_task(feed(), name="buffer")
        airing = asyncio.create_task(
            supervisor.supervise("broadcast", self._broadcast), name="broadcast"
        )
        stopping = asyncio.create_task(self._stop.wait(), name="stop")
        await asyncio.wait({airing, stopping}, return_when=asyncio.FIRST_COMPLETED)
        reason = ExitReason.STOPPED
        if airing.done() and not airing.cancelled():
            reason = (
                ExitReason.FINISHED if airing.result() is Outcome.COMPLETED else ExitReason.FAILED
            )
        for task in (airing, feeding, stopping):
            task.cancel()
        await asyncio.gather(airing, feeding, stopping, return_exceptions=True)
        self._health.update(restarts=sum(supervisor.restarts.values()))
        return reason

    # ------------------------------------------------------------------------------- broadcast

    async def _broadcast(self) -> None:
        """Air the programme from the cursor onward; filler when the buffer is behind."""
        assert self._buffer is not None  # noqa: S101 - set before the tasks start
        buffer = self._buffer
        while True:
            buffer.changed.clear()
            finished = buffer.finished  # read first: it is set only after the last day is stored
            cursor = await asyncio.to_thread(self._read_cursor)
            blocks = await asyncio.to_thread(self._pending, cursor)
            if not blocks:
                if finished:
                    return
                await self._wait_for_blocks(buffer)
                continue
            for block in blocks:
                await self._air(block, cursor)

    async def _air(self, block: Block, cursor: Cursor | None) -> None:
        assert self._player is not None  # noqa: S101
        assert self._buffer is not None  # noqa: S101
        resuming = (
            cursor is not None
            and cursor.phase is Phase.STARTED
            and cursor.block == block.id
            and block.kind is BlockKind.MATCH
        )
        await self._player.play(block, cursor.after_seq if resuming and cursor else NO_EVENT)
        if block.kind is BlockKind.MATCHDAY_MAGAZINE:
            self._buffer.aired_matchday()
        self._health.update(
            buffer_ready_blocks=self._buffer.ready,
            buffer_low=self._buffer.ready == 0,
            quarantined=len(self._buffer.quarantined),
        )

    async def _wait_for_blocks(self, buffer: SimulationBuffer) -> None:
        """Wait (in real time) for the buffer; air filler if it does not deliver in time."""
        assert self._player is not None  # noqa: S101
        try:
            await asyncio.wait_for(buffer.changed.wait(), self._config.starve_grace_s)
        except TimeoutError:
            self._fillers += 1
            filler = Block(
                filler_id(self._fillers),
                BlockKind.FILLER,
                "",
                self._config.programme.filler_s,
                {"reason": "buffer_low"},
            )
            self._health.update(buffer_low=True)
            await self._player.play(filler)

    # -------------------------------------------------------------------------- stored state

    def _make_player(self, bus: EventBus) -> MatchPlayer:
        return MatchPlayer(
            clock=self._parts.clock,
            bus=bus,
            programme=self._config.programme,
            load_events=self._load_events,
            persist=self._persist,
            health=self._health,
            cursor_every=self._config.cursor_every,
            max_lag_s=self._config.max_lag_s,
        )

    def _read_cursor(self) -> Cursor | None:
        with self._parts.factory() as uow:
            return load_cursor(uow)

    def _pending(self, cursor: Cursor | None) -> list[Block]:
        assert self._buffer is not None  # noqa: S101
        with self._parts.factory() as uow:
            blocks = build_programme(uow, self._config.programme, self._buffer.quarantined)
        return after(blocks, cursor)

    async def _persist(self, cursor: Cursor) -> None:
        await asyncio.to_thread(self._save_cursor, cursor)

    def _save_cursor(self, cursor: Cursor) -> None:
        with self._save_lock, self._parts.factory() as uow:
            advance_cursor(uow, cursor)
            uow.commit()

    async def _load_events(self, match_id: str) -> Sequence[MatchEvent]:
        return await asyncio.to_thread(self._events_of, match_id)

    def _events_of(self, match_id: str) -> list[MatchEvent]:
        with self._parts.factory() as uow:
            return [row.event for row in uow.events.find({"match_id": match_id}, order_by="seq")]

    def _next_run(self) -> int:
        with self._parts.factory() as uow:
            entry = uow.meta.get(RUNS_KEY)
            number = (int(entry.value) if entry is not None else 0) + 1
            uow.meta.save(MetaEntry(key=RUNS_KEY, value=str(number)))
            uow.commit()
        return number

    # ------------------------------------------------------------------------------- markers

    async def _announce(self, run_number: int, cursor: Cursor | None) -> None:
        assert self._bus is not None  # noqa: S101
        resuming = cursor is not None and cursor.phase is Phase.STARTED
        marker = EngineMarker(
            id=f"marker:{run_number:04d}:{'resume' if resuming else 'start'}",
            marker=MarkerKind.RESUME if resuming else MarkerKind.START,
            detail=f"run {run_number}",
            resume_match_id=None,
            resume_after_seq=cursor.after_seq if cursor is not None and resuming else None,
        )
        await self._bus.emit(marker)

    async def _announce_stop(self, run_number: int, reason: ExitReason) -> None:
        assert self._bus is not None  # noqa: S101
        marker = EngineMarker(
            id=f"marker:{run_number:04d}:stop", marker=MarkerKind.STOP, detail=reason.value
        )
        await self._bus.emit(marker)

    @staticmethod
    def _sink_stats(bus: EventBus) -> dict[str, dict[str, int]]:
        return {
            name: {"delivered": s.delivered, "dropped": s.dropped, "lost": s.lost}
            for name, s in bus.stats().items()
        }
