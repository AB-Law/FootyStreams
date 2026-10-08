"""The playback cursor: where the broadcast had got to, kept in the database.

A crash can happen at any instant, so the engine records its progress as it goes and a restart
picks up from there. The cursor names the last programme block it touched and how far into it:

* ``phase = started`` and ``after_seq = n``: the block was running and events up to ``n`` were
  delivered; a match block resumes at event ``n + 1``, a segment starts again (its ids are stable,
  so a consumer drops the repeat);
* ``phase = done``: the block finished; the next block is next.

Block ids sort in broadcast order (``date:matchday:fixture:ordinal``), so "everything after the
cursor" is a comparison of strings. The cursor is saved every ``cursor_every`` events, not on every
one, which makes replay after a crash at-least-once within that window: sinks see the same
``(match_id, seq)`` ids again, preceded by a ``resume`` marker.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from footystreams.persistence.ports import NotFoundError, Repositories
from footystreams.persistence.records import MetaEntry

CURSOR_KEY = "engine_cursor"
NO_EVENT = -1


class Phase(StrEnum):
    """Whether the block named by the cursor is still running."""

    STARTED = "started"
    DONE = "done"


@dataclass(frozen=True, slots=True)
class Cursor:
    """The last block touched, whether it finished and the last event delivered within it."""

    block: str
    phase: Phase
    after_seq: int = NO_EVENT

    def encode(self) -> str:
        """The JSON stored in the database."""
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def decode(cls, text: str) -> Cursor:
        """Read a stored cursor; a damaged one raises ``ValueError``."""
        try:
            raw = json.loads(text)
            return cls(str(raw["block"]), Phase(raw["phase"]), int(raw["after_seq"]))
        except (ValueError, KeyError, TypeError) as error:
            msg = f"damaged engine cursor {text!r}"
            raise ValueError(msg) from error


def load_cursor(repositories: Repositories) -> Cursor | None:
    """The saved cursor, or None for an engine that has never played anything."""
    entry = repositories.meta.get(CURSOR_KEY)
    if entry is None:
        return None
    return Cursor.decode(entry.value)


def save_cursor(repositories: Repositories, cursor: Cursor) -> None:
    """Store the cursor (the caller commits)."""
    repositories.meta.save(MetaEntry(key=CURSOR_KEY, value=cursor.encode()))


def require_cursor(repositories: Repositories) -> Cursor:
    """The saved cursor; raises ``NotFoundError`` if there is none."""
    cursor = load_cursor(repositories)
    if cursor is None:
        raise NotFoundError("world_meta", CURSOR_KEY)
    return cursor
