"""E12: the real ``engine`` process, stopped and started again, airs one continuous broadcast.

Start the process on a new database, read its NDJSON from stdout while a match is on air, stop it
(a graceful signal, or a hard kill that gives it no chance to clean up), start it again on the same
database and let it finish. Whatever the first process had delivered plus whatever the second
delivers, with repeated ids dropped, is exactly what an uninterrupted run delivers: nothing lost,
nothing out of order, nothing extra. The repeats are bounded by the cursor interval.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from footystreams.events.broadcast import EngineMarker, MarkerKind, from_line
from footystreams.seed.world_io import write_world
from tests.factories.world import make_world

pytestmark = [pytest.mark.slow, pytest.mark.timeout(420)]
UNTIL = "2031-08-15"  # the first matchday of the seed-2, four-club world
CURSOR_EVERY = 5


class Process:
    """A running engine whose stdout is collected on a thread."""

    def __init__(self, directory: Path, db: Path, pace: str) -> None:
        arguments = [
            sys.executable, "-m", "footystreams.cli.engine", "--db", str(db),
            "--world", str(directory / "world"), "--pace", pace, "--until-date", UNTIL,
            "--cursor-every", str(CURSOR_EVERY), "--starve-grace-s", "120", "--log-level", "ERROR",
        ]  # fmt: skip
        self._errors = (directory / f"{db.stem}.{pace.replace(':', '_')}.err").open("w")
        flags = 0
        if sys.platform == "win32":  # an if statement: mypy skips it where the name is missing
            flags = subprocess.CREATE_NEW_PROCESS_GROUP
        self.process = subprocess.Popen(  # noqa: S603 - our own interpreter, fixed arguments
            arguments, stdout=subprocess.PIPE, stderr=self._errors, text=True, creationflags=flags
        )
        self.lines: list[str] = []
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.append(line.rstrip("\n"))

    def wait_for(self, count_of: str, at_least: int, timeout_s: float = 150.0) -> None:
        """Block until at least ``at_least`` output lines contain ``count_of``."""
        deadline = time.monotonic() + timeout_s
        while sum(count_of in line for line in self.lines) < at_least:
            if time.monotonic() > deadline or self.process.poll() is not None:
                msg = f"never saw {at_least} x {count_of!r} (exit {self.process.poll()})"
                raise AssertionError(msg)
            time.sleep(0.02)

    def stop_gracefully(self) -> int:
        """Ask the process to stop the way an operator or a supervisor would."""
        if sys.platform == "win32":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.process.terminate()
        return self.finish()

    def kill(self) -> int:
        """End the process with no chance to clean up (power cut, OOM kill)."""
        self.process.kill()
        return self.finish()

    def finish(self, timeout_s: float = 200.0) -> int:
        """Wait for the process and the reader thread to end; returns the exit code."""
        code = self.process.wait(timeout=timeout_s)
        self._reader.join(timeout=10)
        self._errors.close()
        return code


def _ids(lines: list[str]) -> list[str]:
    return [from_line(line).id for line in lines if line.strip()]


def _without_markers(lines: list[str]) -> list[str]:
    return [i for i in _ids(lines) if not i.startswith("marker:")]


@pytest.fixture(scope="module")
def world_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("e12")
    write_world(make_world(2, 4), directory / "world")
    return directory


@pytest.fixture(scope="module")
def reference(world_directory: Path) -> list[str]:
    """What an uninterrupted run over the same world broadcasts."""
    run = Process(world_directory, world_directory / "reference.sqlite", "instant")
    assert run.finish() == 0
    return _without_markers(run.lines)


@pytest.mark.parametrize("how", ["graceful", "kill"])
def test_engine_process__stopped_mid_match_and_started_again_it_airs_one_continuous_broadcast(
    world_directory: Path, reference: list[str], how: str
) -> None:
    db = world_directory / f"{how}.sqlite"
    first = Process(world_directory, db, "scaled:3000")
    first.wait_for('"seq":', 120)  # well into the first match
    code = first.stop_gracefully() if how == "graceful" else first.kill()
    if how == "graceful":
        assert code == 0
    second = Process(world_directory, db, "instant")
    assert second.finish() == 0

    combined = _without_markers(first.lines) + _without_markers(second.lines)
    unique = list(dict.fromkeys(combined))
    assert unique == reference
    assert len(combined) - len(unique) <= CURSOR_EVERY + 1  # repeats stay inside the replay window
    resume = from_line(second.lines[0])
    assert isinstance(resume, EngineMarker)
    assert resume.marker is MarkerKind.RESUME
    last = from_line(second.lines[-1])
    assert isinstance(last, EngineMarker)
    assert last.marker is MarkerKind.STOP
