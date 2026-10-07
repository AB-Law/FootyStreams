"""The log digest: SHA-256 of the NDJSON of a sequence of events.

One implementation shared by the simulator (which records it) and `verify` (which recomputes it).
Each line is the event's `model_dump_json()`: keys in field-declaration order, floats as shortest
round-trip decimals, no whitespace. That is a pure function of the validated model, so the digest
is stable across platforms (pydantic is pinned in uv.lock), and about 7x faster than sorting keys
through `canonical_json` (Perf: M4-digest, 70 ms -> 10 ms per match).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from footystreams.events.types import MatchEvent


def event_line(event: MatchEvent) -> str:
    """Return one event as a compact JSON line (no trailing newline)."""
    return event.model_dump_json()


def log_digest(events: Iterable[MatchEvent]) -> str:
    """Return the hex SHA-256 over every event's canonical line followed by a newline."""
    digest = hashlib.sha256()
    for event in events:
        digest.update(event_line(event).encode())
        digest.update(b"\n")
    return digest.hexdigest()
