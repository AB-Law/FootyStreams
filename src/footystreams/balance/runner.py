"""Play scenarios on the real simulator, across processes, and return their samples in order.

The scenarios are shipped to each worker once (the pool initializer); a task is then just a
config and a slice of indices. Results are concatenated in slice order, so the sample list is a
pure function of (scenarios, config) whatever the worker count: ``--workers 1`` and ``--workers 8``
give identical numbers.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from types import TracebackType
from typing import Self

from footystreams.balance.sample import MatchSample, sample_from
from footystreams.balance.scenarios import Scenario
from footystreams.sim import SimConfig, run_match
from footystreams.sim.tables import StaticTables

CHUNKS_PER_WORKER = 4  # more chunks than workers keeps them busy when matches vary in cost


@dataclass(frozen=True, slots=True)
class _Context:
    scenarios: Sequence[Scenario]
    tables: StaticTables


_CONTEXT: _Context | None = None


def _install(context: _Context) -> None:
    global _CONTEXT  # noqa: PLW0603 - the per-process state a pool initializer sets
    _CONTEXT = context


def _play(context: _Context, config: SimConfig, start: int, stop: int) -> list[MatchSample]:
    samples = []
    for scenario in context.scenarios[start:stop]:
        result = run_match(scenario.setup, scenario.seed, config, context.tables)
        samples.append(sample_from(result, scenario.gap))
    return samples


def _play_in_worker(config: SimConfig, start: int, stop: int) -> list[MatchSample]:
    if _CONTEXT is None:
        msg = "balance worker started without its scenarios"
        raise RuntimeError(msg)
    return _play(_CONTEXT, config, start, stop)


def play_only(config: SimConfig) -> SimConfig:
    """``config`` without the causal context and event enrichment, which nothing in play reads.

    # Perf: M8-balance-run - context and enrichment cost about 15% of a match and feed only the
    # summary's maps, tags and ratings; no balance metric reads them. The samples are identical
    # with and without (tests/unit/balance/test_balance_runner.py), so the harness skips them.
    """
    return config.model_copy(
        update={"context": config.context.model_copy(update={"enabled": False})}
    )


def default_workers() -> int:
    """One worker per core, leaving one free for the machine."""
    return max(1, (os.cpu_count() or 1) - 1)


def _slices(count: int, parts: int) -> list[tuple[int, int]]:
    size = -(-count // parts)
    return [(start, min(start + size, count)) for start in range(0, count, size)]


class BalanceRunner:
    """Plays a fixed list of scenarios under any config; reuse it to compare configs."""

    def __init__(self, scenarios: Sequence[Scenario], tables: StaticTables, workers: int) -> None:
        """Start ``workers`` processes (none when ``workers`` is 1: matches run in this process)."""
        self._context = _Context(scenarios, tables)
        self._workers = workers
        self._pool = (
            ProcessPoolExecutor(workers, initializer=_install, initargs=(self._context,))
            if workers > 1
            else None
        )

    def __enter__(self) -> Self:
        """Use as a context manager so the pool is always shut down."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Shut the pool down."""
        if self._pool is not None:
            self._pool.shutdown()

    def run(self, config: SimConfig) -> list[MatchSample]:
        """Play every scenario with ``config``; samples follow scenario order."""
        config = play_only(config)
        count = len(self._context.scenarios)
        if self._pool is None or count == 0:
            return _play(self._context, config, 0, count)
        slices = _slices(count, self._workers * CHUNKS_PER_WORKER)
        futures = [self._pool.submit(_play_in_worker, config, a, b) for a, b in slices]
        return [sample for future in futures for sample in future.result()]
