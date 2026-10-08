from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest

from footystreams.events.broadcast import (
    BroadcastEvent,
    EngineMarker,
    MarkerKind,
    SegmentStartedEvent,
)
from footystreams.league.clock import read_date
from footystreams.league.daily import DayReport
from footystreams.runtime.cursor import Phase, load_cursor
from footystreams.runtime.engine import Engine, ExitReason
from footystreams.runtime.health import read_health
from footystreams.runtime.lock import AlreadyRunningError, InstanceLock
from footystreams.runtime.sinks import InMemorySink
from tests.factories.engine_rig import Rig

pytestmark = pytest.mark.timeout(120)


def _run(engine: Engine) -> ExitReason:
    return asyncio.run(engine.run())


def _ids(events: list[BroadcastEvent]) -> list[str]:
    return [event.id for event in events if event.type != "engine_marker"]


def _match_events(events: list[BroadcastEvent]) -> list[BroadcastEvent]:
    return [event for event in events if hasattr(event, "seq")]


def _match_id(event: BroadcastEvent) -> str:
    return str(getattr(event, "match_id", ""))


def _marker_kinds(events: list[BroadcastEvent]) -> list[MarkerKind]:
    return [event.marker for event in events if isinstance(event, EngineMarker)]


def _segments(events: list[BroadcastEvent]) -> list[SegmentStartedEvent]:
    return [event for event in events if isinstance(event, SegmentStartedEvent)]


def _no_violations(events: Any, setup: Any = None) -> list[str]:
    return []


def _thin_rig(directory: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    """A rig with short match logs and verification switched off (see ``Rig``)."""
    monkeypatch.setattr("footystreams.runtime.buffer.verify_match", _no_violations)
    return Rig(directory, thin=True)


def _reference(directory: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The ids of an uninterrupted run over the first matchday."""
    rig = _thin_rig(directory, monkeypatch)
    until = rig.matchday_dates()[0]
    assert _run(rig.engine(rig.config(until_date=until))) is ExitReason.FINISHED
    return _ids(rig.sink.events)


class StopWhen(InMemorySink):
    """An archive that asks its engine to stop when a condition on what it has seen holds."""

    def __init__(self, condition: Any) -> None:
        super().__init__(critical=True)
        self.engine: Engine | None = None
        self._condition = condition

    async def write(self, event: BroadcastEvent) -> None:
        await super().write(event)
        if self.engine is not None and self._condition(self.events):
            self.engine.request_stop()


def _second_match_has_started(events: list[BroadcastEvent]) -> bool:
    matches: list[str] = []
    for event in _match_events(events):
        match_id = event.match_id  # type: ignore[union-attr]
        if match_id not in matches:
            matches.append(match_id)
        if len(matches) == 2 and getattr(event, "seq", 0) >= 4:
            return True
    return False


# ---------------------------------------------------------------------------------- a finite run


@pytest.mark.slow
def test_engine__a_finite_run_airs_the_programme_between_a_start_and_a_stop(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    until = rig.matchday_dates()[0]

    reason = _run(rig.engine(rig.config(until_date=until)))

    events = rig.sink.events
    assert reason is ExitReason.FINISHED
    assert (events[0].type, events[-1].type) == ("engine_marker", "engine_marker")
    assert (_marker_kinds(events)[0], _marker_kinds(events)[-1]) == (
        MarkerKind.START,
        MarkerKind.STOP,
    )
    started = [s.block_id for s in _segments(events)]
    ended = [e.block_id for e in events if e.type == "segment_ended"]
    assert started == ended
    kinds = [s.kind.value for s in _segments(events) if not s.block_id.endswith(":ht")]
    assert kinds.count("matchday_magazine") == 1
    assert kinds.count("pre_match") == kinds.count("post_match") == 2


@pytest.mark.slow
def test_engine__every_match_airs_exactly_the_events_that_were_stored(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    until = rig.matchday_dates()[0]
    _run(rig.engine(rig.config(until_date=until)))

    aired: dict[str, list[BroadcastEvent]] = {}
    for event in _match_events(rig.sink.events):
        aired.setdefault(_match_id(event), []).append(event)
    with rig.factory() as uow:
        for match_id, events in aired.items():
            stored = [row.event for row in uow.events.find({"match_id": match_id}, order_by="seq")]
            assert events == stored
    assert len(aired) == 2


@pytest.mark.slow
def test_engine__the_cursor_ends_on_the_last_block_aired_and_the_health_file_says_stopped(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    until = rig.matchday_dates()[0]
    config = rig.config(until_date=until)

    _run(rig.engine(config))

    with rig.factory() as uow:
        cursor = load_cursor(uow)
    health = read_health(config.health_path)
    assert cursor is not None
    assert cursor.phase is Phase.DONE
    assert cursor.block.endswith(":~:9")
    assert health["status"] == "stopped"
    assert health["buffer_low"] is False or health["buffer_ready_blocks"] == 0
    assert health["sinks"]["memory"]["lost"] == 0  # type: ignore[index]


@pytest.mark.slow
def test_engine__a_second_run_numbers_its_markers_after_the_first(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    until = rig.matchday_dates()[0]
    _run(rig.engine(rig.config(until_date=until)))

    rig.sink = InMemorySink(critical=True)
    _run(rig.engine(rig.config(until_date=until)))

    markers = [e for e in rig.sink.events if e.type == "engine_marker"]
    assert [m.id for m in markers] == ["marker:0002:start", "marker:0002:stop"]
    assert _ids(rig.sink.events) == []  # everything had already been aired


# ------------------------------------------------------------------------------ stop and resume


@pytest.mark.slow
@pytest.mark.parametrize("cursor_every", [1, 1000])
def test_engine__stopped_mid_match_it_resumes_where_it_was_and_airs_the_rest_once(
    tmp_path: Path, cursor_every: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _reference(tmp_path / "reference", monkeypatch)
    rig = _thin_rig(tmp_path / "interrupted", monkeypatch)
    until = rig.matchday_dates()[0]
    first = StopWhen(_second_match_has_started)
    rig.sink = first
    config = rig.config(until_date=until, cursor_every=cursor_every)
    engine = rig.engine(config)
    first.engine = engine

    assert _run(engine) is ExitReason.STOPPED
    with rig.factory() as uow:
        cursor = load_cursor(uow)
    assert cursor is not None
    assert cursor.phase is Phase.STARTED

    rig.sink = InMemorySink(critical=True)
    assert _run(rig.engine(config)) is ExitReason.FINISHED

    combined = _ids(first.events) + _ids(rig.sink.events)
    unique = list(dict.fromkeys(combined))
    assert unique == expected
    assert len(combined) - len(unique) <= cursor_every  # repeats stay inside the replay window
    if cursor_every == 1:
        assert combined == expected  # saved after every event: nothing is aired twice
    assert _marker_kinds(rig.sink.events)[0] is MarkerKind.RESUME


def test_engine__a_graceful_stop_returns_stopped_and_leaves_the_lock_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _thin_rig(tmp_path, monkeypatch)
    stopper = StopWhen(lambda events: len(events) >= 5)
    rig.sink = stopper
    config = rig.config()
    engine = rig.engine(config)
    stopper.engine = engine

    assert _run(engine) is ExitReason.STOPPED

    with InstanceLock(config.lock_path):
        pass
    assert read_health(config.health_path)["status"] == "stopped"


def test_engine__a_second_engine_on_the_same_database_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _thin_rig(tmp_path, monkeypatch)
    config = rig.config(lock_grace_s=0.0)

    with InstanceLock(config.lock_path), pytest.raises(AlreadyRunningError):
        _run(rig.engine(config))


# ----------------------------------------------------------------------------------- failure modes


@pytest.mark.slow
def test_engine__a_buffer_that_cannot_keep_up_is_covered_with_filler_and_nothing_stalls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _thin_rig(tmp_path, monkeypatch)
    until = rig.matchday_dates()[0]

    def slow_step() -> DayReport:
        time.sleep(0.12)
        return rig.stepper()

    config = rig.config(until_date=until, starve_grace_s=0.03)

    assert _run(rig.engine(config, step=slow_step)) is ExitReason.FINISHED

    fillers = [s for s in _segments(rig.sink.events) if s.block_id.startswith("filler:")]
    assert fillers
    assert all(s.facts["reason"] == "buffer_low" for s in fillers)
    assert len(_match_events(rig.sink.events)) > 0  # the matches still aired afterwards
    with rig.factory() as uow:
        cursor = load_cursor(uow)
    assert cursor is not None
    assert not cursor.block.startswith("filler:")


class Raising(InMemorySink):
    async def write(self, event: BroadcastEvent) -> None:
        msg = "viewer disconnected"
        raise ConnectionError(msg)


class Slow(InMemorySink):
    async def write(self, event: BroadcastEvent) -> None:
        await asyncio.sleep(0.01)
        await super().write(event)


@pytest.mark.slow
def test_engine__a_failing_or_slow_viewer_never_costs_the_archive_an_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _reference(tmp_path / "reference", monkeypatch)
    rig = _thin_rig(tmp_path / "isolated", monkeypatch)
    until = rig.matchday_dates()[0]
    config = rig.config(until_date=until, sink_queue=3)
    broken, slow = Raising("viewer"), Slow("slow")

    reason = _run(rig.engine(config, extra_sinks=(broken, slow)))

    sinks = read_health(config.health_path)["sinks"]
    assert reason is ExitReason.FINISHED
    assert _ids(rig.sink.events) == expected
    assert sinks["memory"]["lost"] == 0  # type: ignore[index]
    assert sinks["viewer"]["dropped"] > 0  # type: ignore[index]
    assert sinks["slow"]["dropped"] > 0  # type: ignore[index]


def test_engine__a_match_that_fails_verification_is_replaced_by_filler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, thin=True)
    until = rig.matchday_dates()[0]
    with rig.factory() as uow:
        first_day = sorted(f.id for f in uow.fixtures.all() if f.date == until)
    target = f"mch_{first_day[0].removeprefix('fix_')}"

    def verdict(events: Any, setup: Any = None) -> list[str]:
        return ["a rule was broken"] if events and events[0].match_id == target else []

    monkeypatch.setattr("footystreams.runtime.buffer.verify_match", verdict)
    config = rig.config(until_date=until)

    _run(rig.engine(config))

    assert target not in {_match_id(e) for e in _match_events(rig.sink.events)}
    quarantined = [s for s in _segments(rig.sink.events) if s.facts.get("reason") == "quarantined"]
    assert [s.facts["match_id"] for s in quarantined] == [target]
    assert read_health(config.health_path)["quarantined"] == 1
    with rig.factory() as uow:
        assert target in uow.meta.require("engine_quarantine").value


def test_engine__safe_mode_airs_what_exists_and_never_advances_the_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _thin_rig(tmp_path, monkeypatch)
    stopper = StopWhen(lambda events: any(e.type == "segment_ended" for e in events))
    rig.sink = stopper
    with rig.factory() as uow:
        before = read_date(uow)
    config = rig.config(safe_mode=True, starve_grace_s=0.02)
    engine = rig.engine(config)
    stopper.engine = engine

    assert _run(engine) is ExitReason.STOPPED

    with rig.factory() as uow:
        assert read_date(uow) == before
    assert all(s.block_id.startswith("filler:") for s in _segments(stopper.events))


def test_engine__a_buffer_that_keeps_crashing_opens_the_circuit_and_the_channel_stays_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _thin_rig(tmp_path, monkeypatch)
    calls = [0]

    def broken_step() -> DayReport:
        calls[0] += 1
        msg = "the simulation is down"
        raise RuntimeError(msg)

    stopper = StopWhen(lambda events: sum(e.type == "segment_ended" for e in events) >= 3)
    rig.sink = stopper
    config = rig.config(starve_grace_s=0.02)
    engine = rig.engine(config, step=broken_step)
    stopper.engine = engine

    assert _run(engine) is ExitReason.STOPPED

    health = read_health(config.health_path)
    assert calls[0] == 5  # the supervisor's failure limit
    assert "buffer circuit open" in health["notes"]  # type: ignore[operator]
    assert health["restarts"] == 4
    assert [s.kind.value for s in _segments(stopper.events)][:3] == ["filler"] * 3


@pytest.mark.slow
@pytest.mark.timeout(300)
def test_engine__a_whole_season_with_the_rollover_runs_in_seconds_on_the_virtual_clock(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, rollover=True)
    started = time.monotonic()

    reason = _run(rig.engine(rig.config(max_seasons=1)))

    kinds = [s.kind.value for s in _segments(rig.sink.events) if not s.block_id.endswith(":ht")]
    assert reason is ExitReason.FINISHED
    assert kinds.count("matchday_magazine") == 6
    assert len({_match_id(e) for e in _match_events(rig.sink.events)}) == 12
    assert rig.clock.now() > 6 * 3600  # hours of programme, not waited out
    assert time.monotonic() - started < 120
