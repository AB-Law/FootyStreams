from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from footystreams.league.clock import read_date
from footystreams.runtime.buffer import QUARANTINE_KEY, Limits, SimulationBuffer
from footystreams.runtime.config import Programme
from footystreams.runtime.cursor import Cursor, Phase
from footystreams.runtime.programme import build_programme
from tests.factories.engine_rig import Rig

pytestmark = pytest.mark.timeout(120)


def _no_violations(events: Any, setup: Any = None) -> list[str]:
    return []


def _rig(directory: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    monkeypatch.setattr("footystreams.runtime.buffer.verify_match", _no_violations)
    return Rig(directory, thin=True)


def _buffer(rig: Rig, limits: Limits) -> SimulationBuffer:
    return SimulationBuffer(
        step=rig.stepper,
        executor=None,
        factory=rig.factory,
        programme=Programme(),
        limits=limits,
    )


def test_world_stepper__plays_one_day_at_a_time_and_prepares_the_season_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _rig(tmp_path, monkeypatch)
    with rig.factory() as uow:
        start = read_date(uow)

    first = rig.stepper()

    with rig.factory() as uow:
        assert read_date(uow) == start + dt.timedelta(days=1)
        assert uow.fixtures.count({}) > 0  # the stepper scheduled the season
    assert first.date == start
    assert first.matches_played == 0


@pytest.mark.slow
def test_buffer__runs_the_world_to_the_first_matchday_then_waits_for_the_broadcast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _rig(tmp_path, monkeypatch)
    buffer = _buffer(rig, Limits(depth=1))

    async def scenario() -> None:
        task = asyncio.create_task(buffer.run())
        await asyncio.wait_for(buffer.changed.wait(), 30)
        await asyncio.sleep(0.2)  # room for it to overrun if it were going to
        assert buffer.ready == 1
        assert not task.done()  # full: it waits for the broadcast
        buffer.aired_matchday()
        await asyncio.wait_for(_until(lambda: buffer.ready == 1), 30)  # and moves on to the next
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


async def _until(condition: Any) -> None:
    while not condition():
        await asyncio.sleep(0.01)


@pytest.mark.slow
def test_buffer__an_until_date_finishes_the_run_after_that_days_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _rig(tmp_path, monkeypatch)
    until = rig.matchday_dates()[0]
    buffer = _buffer(rig, Limits(depth=3, until_date=until))

    asyncio.run(buffer.run())

    assert buffer.finished is True
    assert buffer.ready == 1
    with rig.factory() as uow:
        assert read_date(uow) > until  # the day itself was played


def test_buffer__frozen_never_advances_the_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _rig(tmp_path, monkeypatch)
    with rig.factory() as uow:
        before = read_date(uow)
    buffer = _buffer(rig, Limits(frozen=True))

    asyncio.run(buffer.run())

    with rig.factory() as uow:
        assert read_date(uow) == before
    assert (buffer.ready, buffer.finished) == (0, False)


@pytest.mark.slow
def test_buffer__a_log_with_violations_is_quarantined_and_remembered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, thin=True)
    until = rig.matchday_dates()[0]
    monkeypatch.setattr(
        "footystreams.runtime.buffer.verify_match",
        lambda events, setup=None: ["broken"] if events[0].match_id.endswith("a") else [],
    )
    buffer = _buffer(rig, Limits(until_date=until))

    asyncio.run(buffer.run())

    with rig.factory() as uow:
        stored = uow.meta.get(QUARANTINE_KEY)
        matches = {f.match_id for f in uow.fixtures.find({"date": until})}
    expected = {str(m) for m in matches if str(m).endswith("a")}
    assert buffer.quarantined == expected
    assert (stored is not None) == bool(expected)


@pytest.mark.slow
def test_buffer__prime_counts_the_matchdays_waiting_after_the_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _rig(tmp_path, monkeypatch)
    buffer = _buffer(rig, Limits(depth=5, until_date=rig.matchday_dates()[1]))
    asyncio.run(buffer.run())
    with rig.factory() as uow:
        blocks = build_programme(uow, Programme())
    fresh = _buffer(rig, Limits())

    fresh.prime(None)
    assert fresh.ready == 2

    fresh.prime(Cursor(blocks[6].id, Phase.DONE))  # the first matchday's magazine aired
    assert fresh.ready == 1
    assert fresh.changed.is_set()


@pytest.mark.slow
def test_buffer__a_new_season_in_the_database_counts_as_a_rollover(tmp_path: Path) -> None:
    rig = Rig(tmp_path, thin=True, rollover=True)
    buffer = _buffer(rig, Limits(depth=1, max_seasons=1))
    buffer.prime(None)

    async def scenario() -> None:
        task = asyncio.create_task(buffer.run())
        while not task.done():
            if buffer.ready:
                buffer.aired_matchday()
            await asyncio.sleep(0.005)

    asyncio.run(asyncio.wait_for(scenario(), 110))

    assert buffer.seasons_done == 1
    assert buffer.finished is True
