"""``HealthReporter``: a heartbeat file and structured logs, so the channel can be watched.

The heartbeat is a small JSON file beside the database, replaced atomically on every update, that an
operator or an external supervisor can read without touching the engine: its status, the buffer
depth, the block on air, the sinks' counters and when it last made progress. Wall-clock time is
passed in (``wall``) so tests control it.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path


class Status(StrEnum):
    """The engine's overall state."""

    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass(slots=True)
class HealthState:
    """What the heartbeat file says."""

    status: Status = Status.STARTING
    pid: int = field(default_factory=os.getpid)
    started_at: float = 0.0
    updated_at: float = 0.0
    last_progress_at: float = 0.0
    buffer_ready_blocks: int = 0
    buffer_low: bool = False
    current_block: str = ""
    last_event_id: str = ""
    restarts: int = 0
    quarantined: int = 0
    notes: tuple[str, ...] = ()
    sinks: Mapping[str, Mapping[str, int]] = field(default_factory=dict)


class HealthReporter:
    """Keeps the state and writes it to the heartbeat file."""

    def __init__(self, path: Path, wall: Callable[[], float] = time.time) -> None:
        """Name the heartbeat file; ``wall`` returns unix seconds."""
        self._path = path
        self._wall = wall
        self.state = HealthState(started_at=wall())

    def update(self, **changes: object) -> None:
        """Change fields of the state and write the file."""
        for name, value in changes.items():
            setattr(self.state, name, value)
        self.write()

    def progress(self, block: str, event_id: str) -> None:
        """Note that an event was delivered (not written to disk until the next update)."""
        self.state.current_block = block
        self.state.last_event_id = event_id
        self.state.last_progress_at = self._wall()

    def write(self) -> None:
        """Replace the heartbeat file atomically."""
        self.state.updated_at = self._wall()
        document = asdict(self.state)
        temporary = self._path.with_name(self._path.name + ".tmp")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
        temporary.replace(self._path)


def read_health(path: Path) -> dict[str, object]:
    """The last heartbeat, as written (for ``uv run health`` and tests)."""
    document: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return document


class JsonFormatter(logging.Formatter):
    """One JSON object per log line: time, level, logger, message (and the exception, if any)."""

    def format(self, record: logging.LogRecord) -> str:
        """Render the record as a single line of JSON."""
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, sort_keys=True)
