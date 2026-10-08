"""``MatchPlayer``: air one programme block at broadcast pace, and remember where it got to.

A match block replays the *stored, verified* event log, exactly as written: no randomness, nothing
simulated on the live path. Each event is due at its playing second (earlier periods at the length
they really ran) plus the half-time break for the second half; the player sleeps on the channel
clock until then and hands the event to the bus. The half-time break airs as a segment between the
``halftime`` event and the second-half kick-off.

The cursor is saved every ``cursor_every`` events, when a block starts and ends, and if the player
is cancelled, so a restart resumes close to where playback stopped. On resume the first unplayed
event is due at once (nothing waits out the part of the match already aired). If the clock jumps
(sleep and wake, a stalled process) the player re-anchors instead of airing the overdue events in a
burst: it never catches up by more than ``max_lag_s``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from footystreams.events.broadcast import (
    SegmentEndedEvent,
    SegmentKind,
    SegmentStartedEvent,
)
from footystreams.events.clock import period_elapsed_s
from footystreams.events.structure import HalftimeEvent
from footystreams.events.types import MatchEvent
from footystreams.runtime.bus import EventBus
from footystreams.runtime.clock import Clock
from footystreams.runtime.config import Programme
from footystreams.runtime.cursor import NO_EVENT, Cursor, Phase
from footystreams.runtime.health import HealthReporter
from footystreams.runtime.programme import Block, BlockKind

SECOND_HALF = 2
MAX_LAG_S = 5.0

Persist = Callable[[Cursor], Awaitable[None]]
LoadEvents = Callable[[str], Awaitable[Sequence[MatchEvent]]]


def playing_offsets(events: Sequence[MatchEvent], half_time_s: float) -> list[float]:
    """Seconds from kick-off at which each event is due, including the half-time break."""
    lengths: dict[int, int] = {}
    for event in events:
        lengths[event.clock.period] = period_elapsed_s(event.clock)
    offsets = []
    for event in events:
        before = sum(length for period, length in lengths.items() if period < event.clock.period)
        break_s = half_time_s if event.clock.period >= SECOND_HALF else 0.0
        offsets.append(before + period_elapsed_s(event.clock) + break_s)
    return offsets


class MatchPlayer:
    """Plays blocks one after another on the channel clock."""

    def __init__(  # noqa: PLR0913 - the collaborators of one player, injected
        self,
        *,
        clock: Clock,
        bus: EventBus,
        programme: Programme,
        load_events: LoadEvents,
        persist: Persist,
        health: HealthReporter | None = None,
        cursor_every: int = 25,
        max_lag_s: float = MAX_LAG_S,
    ) -> None:
        """Create a player; every collaborator is passed in (nothing global)."""
        self._clock = clock
        self._bus = bus
        self._programme = programme
        self._load_events = load_events
        self._persist = persist
        self._health = health
        self._cursor_every = cursor_every
        self._max_lag_s = max_lag_s

    async def play(self, block: Block, resume_after: int = NO_EVENT) -> None:
        """Air ``block``; ``resume_after`` is the last match event already delivered, if any."""
        await self._persist(Cursor(block.id, Phase.STARTED, resume_after))
        if block.kind is BlockKind.MATCH:
            await self._play_match(block, resume_after)
        else:
            await self._play_segment(block)
        await self._persist(Cursor(block.id, Phase.DONE))

    async def _play_segment(self, block: Block) -> None:
        start = self._clock.now()
        await self._bus.emit(
            SegmentStartedEvent(
                id=f"{block.id}:start",
                block_id=block.id,
                kind=block.kind.segment,
                subject_ref=block.subject_ref,
                duration_s=block.duration_s,
                facts=block.facts,
            )
        )
        await self._clock.sleep_until(start + block.duration_s)
        await self._bus.emit(
            SegmentEndedEvent(id=f"{block.id}:end", block_id=block.id, kind=block.kind.segment)
        )

    async def _play_match(self, block: Block, resume_after: int) -> None:
        events = await self._load_events(block.subject_ref)
        offsets = playing_offsets(events, self._programme.half_time_s)
        todo = [i for i, event in enumerate(events) if event.seq > resume_after]
        if not todo:
            return
        anchor = self._clock.now() - offsets[todo[0]]  # the first unplayed event is due now
        delivered, since_save, in_break = resume_after, 0, False
        try:
            for index in todo:
                event = events[index]
                anchor = await self._wait_for(anchor + offsets[index], anchor, offsets[index])
                if in_break and event.clock.period >= SECOND_HALF:
                    await self._end_break(block)
                    in_break = False
                await self._bus.emit(event)
                delivered, since_save = event.seq, since_save + 1
                self._note(block, event.id)
                if isinstance(event, HalftimeEvent):
                    await self._start_break(block, event)
                    in_break = True
                if since_save >= self._cursor_every:
                    await self._persist(Cursor(block.id, Phase.STARTED, delivered))
                    since_save = 0
        except asyncio.CancelledError:
            await asyncio.shield(self._persist(Cursor(block.id, Phase.STARTED, delivered)))
            raise

    async def _wait_for(self, due: float, anchor: float, offset: float) -> float:
        """Sleep until ``due``; returns the (possibly re-anchored) start of the block's timeline."""
        lag = self._clock.now() - due
        if lag > self._max_lag_s:
            return self._clock.now() - offset  # the clock jumped: pace from here, no burst
        await self._clock.sleep_until(due)
        return anchor

    def _note(self, block: Block, event_id: str) -> None:
        if self._health is not None:
            self._health.progress(block.id, event_id)

    async def _start_break(self, block: Block, halftime: HalftimeEvent) -> None:
        facts = {
            **block.facts,
            "score_home": halftime.score_home,
            "score_away": halftime.score_away,
        }
        await self._bus.emit(
            SegmentStartedEvent(
                id=f"{block.id}:ht:start",
                block_id=f"{block.id}:ht",
                kind=SegmentKind.HALF_TIME,
                subject_ref=block.subject_ref,
                duration_s=self._programme.half_time_s,
                facts=facts,
            )
        )

    async def _end_break(self, block: Block) -> None:
        await self._bus.emit(
            SegmentEndedEvent(
                id=f"{block.id}:ht:end", block_id=f"{block.id}:ht", kind=SegmentKind.HALF_TIME
            )
        )
