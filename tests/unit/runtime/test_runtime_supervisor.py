from __future__ import annotations

import asyncio

import pytest

from footystreams.runtime.supervisor import Outcome, Supervisor

pytestmark = pytest.mark.timeout(30)


class Sleeps:
    """Records the pauses instead of waiting them out."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


class Flaky:
    """A task that raises for its first ``failures`` runs, then completes."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.runs = 0

    async def __call__(self) -> None:
        self.runs += 1
        if self.runs <= self.failures:
            msg = "boom"
            raise RuntimeError(msg)


def test_supervise__a_task_that_completes_is_left_alone() -> None:
    task, sleeps = Flaky(0), Sleeps()

    outcome = asyncio.run(Supervisor(sleep=sleeps).supervise("t", task))

    assert (outcome, task.runs, sleeps.seconds) == (Outcome.COMPLETED, 1, [])


def test_supervise__a_crashing_task_is_restarted_after_a_growing_pause() -> None:
    task, sleeps = Flaky(3), Sleeps()
    supervisor = Supervisor(sleep=sleeps, backoff_start_s=1.0, backoff_cap_s=30.0)

    outcome = asyncio.run(supervisor.supervise("buffer", task))

    assert outcome is Outcome.COMPLETED
    assert task.runs == 4
    assert sleeps.seconds == [1.0, 2.0, 4.0]
    assert supervisor.restarts["buffer"] == 3


def test_supervise__the_pause_stops_growing_at_the_cap() -> None:
    sleeps = Sleeps()
    supervisor = Supervisor(sleep=sleeps, max_failures=9, backoff_start_s=1.0, backoff_cap_s=5.0)

    asyncio.run(supervisor.supervise("t", Flaky(6)))

    assert sleeps.seconds == [1.0, 2.0, 4.0, 5.0, 5.0, 5.0]


def test_supervise__repeated_failure_opens_the_circuit_instead_of_looping() -> None:
    task, sleeps = Flaky(10_000), Sleeps()

    outcome = asyncio.run(Supervisor(sleep=sleeps, max_failures=4).supervise("t", task))

    assert outcome is Outcome.CIRCUIT_OPEN
    assert task.runs == 4
    assert len(sleeps.seconds) == 3


def test_supervise__a_long_healthy_run_resets_the_failure_count() -> None:
    now = [0.0]

    def monotonic() -> float:
        return now[0]

    runs = [0]

    async def task() -> None:
        runs[0] += 1
        now[0] += 100.0  # every run lasts longer than the healthy window
        if runs[0] < 20:
            msg = "boom"
            raise RuntimeError(msg)

    supervisor = Supervisor(
        sleep=Sleeps(), max_failures=3, healthy_after_s=60.0, monotonic=monotonic
    )

    assert asyncio.run(supervisor.supervise("t", task)) is Outcome.COMPLETED
    assert runs[0] == 20


def test_supervise__cancellation_is_not_swallowed() -> None:
    async def scenario() -> None:
        async def forever() -> None:
            await asyncio.sleep(3600)

        task = asyncio.create_task(Supervisor(sleep=Sleeps()).supervise("t", forever))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
