"""``Supervisor``: keep a task alive, with backoff, and give up loudly rather than loop forever.

``supervise`` runs a task factory to completion. If the task raises it is started again after an
exponentially growing pause (capped); if it fails ``max_failures`` times without ever running
``healthy_after_s`` in between, the circuit opens and ``supervise`` returns instead of restarting,
so the engine can fall back to a degraded mode and say so. Cancellation is never swallowed: a
shutdown cancels the task and the cancel propagates.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from enum import StrEnum

LOGGER = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]


class Outcome(StrEnum):
    """How a supervised task ended."""

    COMPLETED = "completed"
    CIRCUIT_OPEN = "circuit_open"


class Supervisor:
    """Restarts crashing tasks with exponential backoff and a circuit breaker."""

    def __init__(  # noqa: PLR0913 - the supervision policy, all with defaults
        self,
        *,
        sleep: Sleep = asyncio.sleep,
        max_failures: int = 5,
        backoff_start_s: float = 1.0,
        backoff_cap_s: float = 30.0,
        healthy_after_s: float = 60.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Set the policy; ``sleep`` and ``monotonic`` are injectable for tests."""
        self._sleep = sleep
        self._max_failures = max_failures
        self._backoff_start_s = backoff_start_s
        self._backoff_cap_s = backoff_cap_s
        self._healthy_after_s = healthy_after_s
        self._monotonic = monotonic
        self.restarts: Counter[str] = Counter()

    async def supervise(self, name: str, factory: Callable[[], Awaitable[None]]) -> Outcome:
        """Run ``factory()`` until it returns; restart it when it raises."""
        failures, backoff = 0, self._backoff_start_s
        while True:
            started = self._monotonic()
            try:
                await factory()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("task %s crashed", name)
                if self._monotonic() - started >= self._healthy_after_s:
                    failures, backoff = 0, self._backoff_start_s  # it ran fine for a while
                failures += 1
                if failures >= self._max_failures:
                    LOGGER.critical("task %s failed %d times: circuit open", name, failures)
                    return Outcome.CIRCUIT_OPEN
                self.restarts[name] += 1
                await self._sleep(backoff)
                backoff = min(backoff * 2, self._backoff_cap_s)
            else:
                return Outcome.COMPLETED
