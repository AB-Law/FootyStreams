"""A single-instance lock: two engines on one database would double-play the same world.

The lock is an operating-system file lock on a file beside the database, taken without waiting.
Because the OS drops the lock when its process ends, a crash (even a power cut) cannot leave a stale
lock behind, which a pid file could not promise. The holder writes its pid after the locked byte so
a refused second engine can say who has the lock.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import IO, Self

LOCKED_BYTES = 1  # the lock covers the first byte; the pid text follows it
RETRY_S = 0.05


class AlreadyRunningError(RuntimeError):
    """Another engine holds the lock on this database."""


if sys.platform == "win32":
    import msvcrt

    def _try_lock(handle: IO[str]) -> bool:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, LOCKED_BYTES)
        except OSError:
            return False
        return True

    def _unlock(handle: IO[str]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, LOCKED_BYTES)

else:
    import fcntl

    def _try_lock(handle: IO[str]) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(handle: IO[str]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _holder(path: Path) -> str:
    """The pid the holder wrote after the locked byte (the locked byte itself cannot be read)."""
    try:
        with path.open("rb") as handle:
            handle.seek(LOCKED_BYTES)
            text = handle.read().decode("utf-8").strip()
    except OSError:
        return "unknown"
    return text or "unknown"


class InstanceLock:
    """Hold the lock for the life of the ``with`` block (or between ``acquire`` and ``release``)."""

    def __init__(self, path: Path) -> None:
        """Name the lock file; nothing is created until ``acquire``."""
        self._path = path
        self._handle: IO[str] | None = None

    def acquire(self, grace_s: float = 0.0) -> None:
        """Take the lock or raise ``AlreadyRunningError`` naming the holder's pid.

        The system releases a dead process's lock a moment after it exits, so a restart right after
        a crash can ask for ``grace_s`` seconds of patience before it is refused.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        deadline = time.monotonic() + grace_s
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                handle.close()
                msg = f"another engine is running on this database (pid {_holder(self._path)})"
                raise AlreadyRunningError(msg)
            time.sleep(RETRY_S)
        handle.seek(LOCKED_BYTES)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        """Drop the lock; safe to call twice."""
        if self._handle is None:
            return
        _unlock(self._handle)
        self._handle.close()
        self._handle = None

    def __enter__(self) -> Self:
        """Take the lock."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Drop the lock."""
        self.release()
