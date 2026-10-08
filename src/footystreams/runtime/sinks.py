"""The built-in sinks: in memory (tests), NDJSON to a stream (stdout), NDJSON to a rotating file.

NDJSON is one ``BroadcastEvent`` per line (``events.broadcast.to_line``), so whatever sits
downstream can be a pipe, ``jq`` or a future WebSocket adapter. Blocking writes run in a worker
thread so a slow pipe never stops the event loop.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TextIO

from footystreams.events.broadcast import BroadcastEvent, to_line
from footystreams.runtime.bus import EventSink

STDOUT_SPEC = "ndjson:stdout"
FILE_PREFIX = "ndjson:file:"
MEMORY_SPEC = "memory"


class InMemorySink:
    """Keeps every event in a list (tests, and a tap for the health report)."""

    def __init__(self, name: str = "memory", *, critical: bool = False) -> None:
        """Create an empty sink."""
        self.name = name
        self.critical = critical
        self.events: list[BroadcastEvent] = []

    async def write(self, event: BroadcastEvent) -> None:
        """Append the event."""
        self.events.append(event)

    async def close(self) -> None:
        """Nothing to release."""


class NdjsonStreamSink:
    """One JSON line per event to a text stream, flushed after every line."""

    def __init__(
        self, stream: TextIO, name: str = "ndjson:stdout", *, critical: bool = False
    ) -> None:
        """Wrap an open text stream; the sink never closes it."""
        self.name = name
        self.critical = critical
        self._stream = stream

    def _write_line(self, line: str) -> None:
        self._stream.write(line + "\n")
        self._stream.flush()

    async def write(self, event: BroadcastEvent) -> None:
        """Write one line without blocking the loop."""
        await asyncio.to_thread(self._write_line, to_line(event))

    async def close(self) -> None:
        """Flush what is left; the stream stays open for its owner."""
        await asyncio.to_thread(self._stream.flush)


class NdjsonFileSink:
    """Appends NDJSON to a file, starting a numbered new file past ``rotate_bytes``."""

    def __init__(
        self, path: Path, *, rotate_bytes: int | None = None, critical: bool = True
    ) -> None:
        """Open (append) the file; it is the archive, so it is critical by default."""
        self.name = f"ndjson:file:{path}"
        self.critical = critical
        self._base = path
        self._rotate_bytes = rotate_bytes
        self._part = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("a", encoding="utf-8")

    def _write_line(self, line: str) -> None:
        if self._rotate_bytes is not None and self._handle.tell() >= self._rotate_bytes:
            self._handle.close()
            self._part += 1
            self._handle = self._base.with_name(f"{self._base.name}.{self._part}").open(
                "a", encoding="utf-8"
            )
        self._handle.write(line + "\n")
        self._handle.flush()

    async def write(self, event: BroadcastEvent) -> None:
        """Append one line (rotating first when the file is full)."""
        await asyncio.to_thread(self._write_line, to_line(event))

    async def close(self) -> None:
        """Close the current file."""
        await asyncio.to_thread(self._handle.close)


def build_sinks(specs: tuple[str, ...], stdout: TextIO | None = None) -> list[EventSink]:
    """Sinks from ``--sink`` specs: ``ndjson:stdout``, ``ndjson:file:PATH`` or ``memory``."""
    sinks: list[EventSink] = []
    for spec in specs:
        if spec == STDOUT_SPEC:
            sinks.append(NdjsonStreamSink(stdout or sys.stdout))
        elif spec.startswith(FILE_PREFIX):
            sinks.append(NdjsonFileSink(Path(spec.removeprefix(FILE_PREFIX))))
        elif spec == MEMORY_SPEC:
            sinks.append(InMemorySink())
        else:
            msg = f"unknown sink {spec!r}; use ndjson:stdout, ndjson:file:PATH or memory"
            raise ValueError(msg)
    return sinks
