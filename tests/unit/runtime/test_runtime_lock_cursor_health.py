from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from footystreams.persistence.ports import NotFoundError
from footystreams.runtime.cursor import (
    NO_EVENT,
    Cursor,
    Phase,
    load_cursor,
    require_cursor,
    save_cursor,
)
from footystreams.runtime.health import HealthReporter, JsonFormatter, Status, read_health
from footystreams.runtime.lock import AlreadyRunningError, InstanceLock
from tests.factories.league_db import make_league_db

# --------------------------------------------------------------------------------------- lock


def test_lock__a_second_engine_on_the_same_database_is_refused_with_the_holders_pid(
    tmp_path: Path,
) -> None:
    path = tmp_path / "league.sqlite.lock"

    with InstanceLock(path), pytest.raises(AlreadyRunningError, match=r"pid \d+"):
        InstanceLock(path).acquire()


def test_lock__is_free_again_once_released_and_release_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "x.lock"
    first = InstanceLock(path)
    first.acquire()
    first.release()
    first.release()

    with InstanceLock(path):
        pass


def test_lock__a_killed_holder_leaves_no_stale_lock(tmp_path: Path) -> None:
    path = tmp_path / "crash.lock"
    program = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from footystreams.runtime.lock import InstanceLock\n"
        f"lock = InstanceLock(Path({str(path)!r}))\n"
        "lock.acquire()\n"
        "print('locked', flush=True)\n"
        "time.sleep(60)\n"
    )
    holder = subprocess.Popen(  # noqa: S603 - our own interpreter and a fixed program
        [sys.executable, "-c", program], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(AlreadyRunningError):
            InstanceLock(path).acquire()
    finally:
        holder.kill()
        holder.wait()

    lock = InstanceLock(path)
    lock.acquire(grace_s=5.0)  # the system frees a dead process's lock a moment after it exits
    lock.release()


# ------------------------------------------------------------------------------------- cursor


def test_cursor__round_trips_through_its_stored_text() -> None:
    cursor = Cursor("2031-09-06:001:fix_t00101:1", Phase.STARTED, 41)

    assert Cursor.decode(cursor.encode()) == cursor


@pytest.mark.parametrize(
    "text", ["", "not json", "{}", '{"block": "a", "phase": "paused", "after_seq": 1}']
)
def test_cursor__a_damaged_value_is_a_value_error(text: str) -> None:
    with pytest.raises(ValueError, match="damaged engine cursor"):
        Cursor.decode(text)


def test_cursor__none_is_saved_until_something_is() -> None:
    factory = make_league_db(2, 4)
    with factory() as uow:
        assert load_cursor(uow) is None
        with pytest.raises(NotFoundError):
            require_cursor(uow)
        save_cursor(uow, Cursor("a", Phase.DONE))
        uow.commit()

    with factory() as uow:
        assert load_cursor(uow) == Cursor("a", Phase.DONE, NO_EVENT)


def test_cursor__a_later_save_replaces_the_earlier_one() -> None:
    factory = make_league_db(2, 4)
    with factory() as uow:
        save_cursor(uow, Cursor("a", Phase.STARTED, 5))
        save_cursor(uow, Cursor("a", Phase.STARTED, 30))
        uow.commit()

    with factory() as uow:
        assert require_cursor(uow).after_seq == 30


# ------------------------------------------------------------------------------------- health


def test_health__every_update_replaces_the_heartbeat_file_atomically(tmp_path: Path) -> None:
    path = tmp_path / "league.health.json"
    clock = iter([100.0, 101.0, 102.0, 103.0, 104.0])
    reporter = HealthReporter(path, wall=lambda: next(clock))

    reporter.update(status=Status.RUNNING, buffer_ready_blocks=4)
    reporter.progress("blk_1", "mch_1:00007")
    reporter.update(buffer_low=True)

    document = read_health(path)
    assert document["status"] == "running"
    assert document["buffer_ready_blocks"] == 4
    assert document["buffer_low"] is True
    assert document["current_block"] == "blk_1"
    assert document["last_event_id"] == "mch_1:00007"
    assert document["started_at"] == 100.0
    assert not list(tmp_path.glob("*.tmp"))


def test_health__creates_missing_folders(tmp_path: Path) -> None:
    reporter = HealthReporter(tmp_path / "deep" / "er" / "h.json", wall=lambda: 1.0)

    reporter.write()

    assert (tmp_path / "deep" / "er" / "h.json").is_file()


def test_json_formatter__one_json_object_per_line() -> None:
    record = logging.LogRecord("engine", logging.WARNING, "f.py", 1, "buffer low: %d", (1,), None)

    entry = json.loads(JsonFormatter().format(record))

    assert (entry["level"], entry["logger"], entry["message"]) == (
        "warning",
        "engine",
        "buffer low: 1",
    )


def test_lock__a_grace_period_waits_for_a_holder_that_lets_go(tmp_path: Path) -> None:
    path = tmp_path / "grace.lock"
    holder = InstanceLock(path)
    holder.acquire()
    waiter = InstanceLock(path)

    with pytest.raises(AlreadyRunningError):
        waiter.acquire(grace_s=0.1)

    holder.release()
    waiter.acquire(grace_s=0.1)
    waiter.release()
