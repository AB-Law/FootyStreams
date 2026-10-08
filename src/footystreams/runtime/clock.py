"""The channel's clock: how fast the broadcast timeline runs against the wall.

The engine never reads the time directly. It asks a ``Clock`` where the channel timeline is and
sleeps until a point on it, so the same code runs in real time in production, N times faster in a
rehearsal and instantly in tests (a whole season in seconds). The timeline is in seconds, starts at
zero for a fresh clock and only moves forward.

``VirtualClock`` is single-timeline: sleeping until a time moves it there at once. That is exact
for the one task that paces playback; helper tasks (health, restarts) do not sleep on it.
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    """A forward-moving timeline in seconds that tasks can wait on."""

    def now(self) -> float:
        """Seconds elapsed on the channel timeline."""

    async def sleep_until(self, moment: float) -> None:
        """Return when the timeline reaches ``moment`` (at once if it already has)."""


class SystemClock:
    """Real time: one channel second is one wall-clock second. Immune to wall-clock jumps."""

    def __init__(self) -> None:
        """Start the timeline now."""
        self._origin = time.monotonic()

    def now(self) -> float:
        """Monotonic seconds since the clock was created."""
        return time.monotonic() - self._origin

    async def sleep_until(self, moment: float) -> None:
        """Wait until the timeline reaches ``moment``."""
        while (delay := moment - self.now()) > 0:  # a sleep can end a tick early: look again
            await asyncio.sleep(delay)


class ScaledClock:
    """Real time sped up: ``speed`` channel seconds pass per wall-clock second."""

    def __init__(self, speed: float) -> None:
        """Start the timeline now; ``speed`` must be positive."""
        if speed <= 0:
            msg = f"clock speed must be positive, got {speed}"
            raise ValueError(msg)
        self._speed = speed
        self._origin = time.monotonic()

    def now(self) -> float:
        """Channel seconds since the clock was created."""
        return (time.monotonic() - self._origin) * self._speed

    async def sleep_until(self, moment: float) -> None:
        """Wait until the timeline reaches ``moment``."""
        while (delay := (moment - self.now()) / self._speed) > 0:
            await asyncio.sleep(delay)


class VirtualClock:
    """No waiting at all: sleeping moves the timeline forward and yields once to other tasks."""

    def __init__(self) -> None:
        """Start the timeline at zero."""
        self._now = 0.0

    def now(self) -> float:
        """The virtual time."""
        return self._now

    async def sleep_until(self, moment: float) -> None:
        """Jump to ``moment`` (never backwards)."""
        self._now = max(self._now, moment)
        await asyncio.sleep(0)

    def advance(self, seconds: float) -> None:
        """Move the timeline forward by hand (tests simulating a stall or a clock jump)."""
        if seconds < 0:
            msg = "a clock cannot go backwards"
            raise ValueError(msg)
        self._now += seconds
