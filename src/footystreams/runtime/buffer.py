"""``SimulationBuffer``: keep the world ahead of the broadcast, and keep bad matches off the air.

Nothing is simulated on the live path. This task runs the league's daily tick (which plays, stores
and applies the day's matches) until at least ``depth`` matchdays are waiting to be aired, then
sleeps until the broadcast has consumed one. The tick runs in an executor (a worker process in
production) so the event loop stays free. Every new match log is then run through ``verify_match``;
a match with violations is *quarantined*: the programme airs filler in its place and the health
report counts it (the fallback simulation profile is M14's job).

The run ends when ``max_seasons`` rollovers or ``until_date`` have been reached: ``finished`` is set
and the broadcast drains what is left. ``frozen`` (safe mode) never advances the world at all.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass

from footystreams.domain.fixture import FixtureStatus
from footystreams.league.daily import DayReport
from footystreams.persistence.ports import UnitOfWorkFactory
from footystreams.persistence.records import MetaEntry
from footystreams.runtime.config import Programme
from footystreams.runtime.cursor import Cursor
from footystreams.runtime.programme import BlockKind, after, build_programme
from footystreams.verify import verify_match

LOGGER = logging.getLogger(__name__)
QUARANTINE_KEY = "engine_quarantine"
PLAYED = FixtureStatus.PLAYED.value

Step = Callable[[], DayReport]


@dataclass(frozen=True, slots=True)
class Limits:
    """How far ahead to run and when to stop."""

    depth: int = 1
    max_seasons: int | None = None
    until_date: dt.date | None = None
    frozen: bool = False


class SimulationBuffer:
    """Runs the world ahead of the broadcast (see the module docstring)."""

    def __init__(
        self,
        *,
        step: Step,
        executor: Executor | None,
        factory: UnitOfWorkFactory,
        programme: Programme,
        limits: Limits,
    ) -> None:
        """Create the buffer; ``step`` plays one in-world day and is called in ``executor``."""
        self._step = step
        self._executor = executor
        self._factory = factory
        self._programme = programme
        self._limits = limits
        self.ready = 0
        self.finished = False
        self.failed = False  # the circuit opened: the world no longer advances
        self.seasons_done = 0
        self._seasons_seen = 0  # seasons in the database; a new one means a rollover happened
        self.quarantined: set[str] = set()
        self.changed = asyncio.Event()  # a matchday became ready, or the run finished
        self._room = asyncio.Event()

    # ------------------------------------------------------------------------------- start-up

    def prime(self, cursor: Cursor | None) -> None:
        """Read the stored quarantine list and count the matchdays already waiting (blocking)."""
        with self._factory() as uow:
            entry = uow.meta.get(QUARANTINE_KEY)
            self.quarantined = set(json.loads(entry.value)) if entry is not None else set()
            blocks = after(build_programme(uow, self._programme, self.quarantined), cursor)
            self._seasons_seen = uow.seasons.count()
        self.ready = sum(block.kind is BlockKind.MATCHDAY_MAGAZINE for block in blocks)
        self.ready += bool(blocks) and blocks[-1].kind is not BlockKind.MATCHDAY_MAGAZINE
        self._room.set()
        if self.ready:
            self.changed.set()

    # ----------------------------------------------------------------------------------- loop

    async def run(self) -> None:
        """Advance the world while there is room, until the run is finished."""
        if self._limits.frozen:
            return
        loop = asyncio.get_running_loop()
        while not self.finished:
            if self.ready >= max(1, self._limits.depth):
                self._room.clear()
                await self._room.wait()
                continue
            report = await loop.run_in_executor(self._executor, self._step)
            await self._after_day(report)

    async def _after_day(self, report: DayReport) -> None:
        if report.matches_played:
            await asyncio.to_thread(self._verify_day, report.date)
            self.ready += 1
        self.seasons_done += await asyncio.to_thread(self._new_seasons)
        limits = self._limits
        ended = limits.max_seasons is not None and self.seasons_done >= limits.max_seasons
        ended = ended or (limits.until_date is not None and report.date >= limits.until_date)
        self.finished = ended
        if report.matches_played or self.finished:
            self.changed.set()

    def _new_seasons(self) -> int:
        """How many seasons the rollover has added since last asked (blocking)."""
        with self._factory() as uow:
            count = uow.seasons.count()
        added, self._seasons_seen = count - self._seasons_seen, count
        return max(0, added)

    def aired_matchday(self) -> None:
        """The broadcast finished a matchday: there is room for the world to move on."""
        self.ready = max(0, self.ready - 1)
        self._room.set()

    # ------------------------------------------------------------------------------ verifying

    def _verify_day(self, date: dt.date) -> None:
        """Check the day's match logs; quarantine the bad ones (blocking, its own transaction)."""
        with self._factory() as uow:
            played = uow.fixtures.find({"date": date, "status": PLAYED})
            bad = []
            for fixture in played:
                stored = uow.events.find({"match_id": str(fixture.match_id)}, order_by="seq")
                problems = verify_match([row.event for row in stored])
                if problems:
                    LOGGER.error("match %s quarantined: %s", fixture.match_id, problems[0])
                    bad.append(str(fixture.match_id))
            if bad:
                self.quarantined.update(bad)
                uow.meta.save(
                    MetaEntry(key=QUARANTINE_KEY, value=json.dumps(sorted(self.quarantined)))
                )
                uow.commit()
