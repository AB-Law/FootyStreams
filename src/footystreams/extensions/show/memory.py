"""Host memories: how strong each is today, which ones come to mind, and how new ones are made.

Strength follows ``docs/design/01-entities.md`` section 7: importance times a decay with a half-life
that grows with importance, arousal and every time the memory is recalled. It is pure arithmetic, so
what the hosts remember is reproducible from the bible alone.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.memory import MemoryRecord
from footystreams.domain.types import EntityKind, EntityRef, MemoryId
from footystreams.extensions.show.textutil import fold

HALF_LIFE_DAYS: Mapping[str, float] = {
    "match_moment": 45.0,
    "interview": 75.0,
    "breaking": 40.0,
    "prediction_result": 60.0,
    "opinion": 90.0,
    "running_joke": 120.0,
    "anecdote": 150.0,
}
DEFAULT_HALF_LIFE_DAYS = 60.0
STRENGTH_FLOOR = 0.05
DEFAULT_AROUSAL = 0.5
RECALL_CAP = 5
RECALL_STEP = 0.15
RELEVANCE_STEP = 1.0
RELEVANCE_CAP = 2
MAX_TEXT = 200
MAX_KEY = 80
SLUG_WORDS = 6
MEMORY_CAP = 300
LLM_KINDS = frozenset({"running_joke", "opinion", "anecdote"})


def text_of(memory: MemoryRecord) -> str:
    """The sentence the host remembers."""
    return str(memory.facts.get("text", ""))


def recalls(memory: MemoryRecord) -> int:
    """How many times the host has brought this memory up."""
    return int(memory.facts.get("recalled", 0))


def strength(memory: MemoryRecord, today: dt.date) -> float:
    """How vivid the memory is on ``today``, from 0 to its importance."""
    days = max((today - memory.created_on).days, 0)
    half_life = (
        HALF_LIFE_DAYS.get(memory.kind, DEFAULT_HALF_LIFE_DAYS)
        * (1 + 2 * memory.salience)
        * (1 + 0.5 * DEFAULT_AROUSAL)
        * (1 + RECALL_STEP * min(recalls(memory), RECALL_CAP))
    )
    return float(memory.salience * max(STRENGTH_FLOOR, 0.5 ** (days / half_life)))


def involves(memory: MemoryRecord, host_id: str) -> bool:
    """Whether the host holds the memory or shares it."""
    return str(memory.owner.id) == host_id or host_id in memory.related_ids


def retrieve(
    memories: Iterable[MemoryRecord],
    host_id: str,
    topics: frozenset[str],
    today: dt.date,
    limit: int,
) -> tuple[MemoryRecord, ...]:
    """The memories most likely to come to this host's mind, strongest and most on topic first."""

    def score(memory: MemoryRecord) -> float:
        overlap = min(len(topics.intersection(memory.related_ids)), RELEVANCE_CAP)
        return strength(memory, today) * (1 + RELEVANCE_STEP * overlap)

    mine = [memory for memory in memories if involves(memory, host_id)]
    return tuple(sorted(mine, key=lambda memory: (-score(memory), memory.id))[:limit])


def slug(text: str) -> str:
    """A short key for a sentence, so the same joke told twice is recognised."""
    words = re.findall(r"[a-z0-9]+", fold(text).lower())[:SLUG_WORDS]
    return "-".join(words) or "memory"


def memory_id(number: int) -> str:
    """The id of the ``number``th memory the show has made."""
    return f"mem_{number:07x}"


@dataclass(frozen=True, slots=True)
class MemorySpec:
    """What a new memory is about, before it gets an id and a date."""

    host_id: str
    kind: str
    text: str
    related: Sequence[str] = ()
    salience: float = 0.5
    origin: str = "show"


def make_memory(number: int, today: dt.date, spec: MemorySpec) -> MemoryRecord:
    """A new memory held by ``spec.host_id`` and shared with everyone in ``spec.related``."""
    return MemoryRecord(
        id=MemoryId(memory_id(number)),
        owner=EntityRef(kind=EntityKind.MEDIA, id=spec.host_id),
        kind=spec.kind,
        created_on=today,
        summary_key=f"{spec.kind}:{slug(spec.text)}"[:MAX_KEY],
        facts={
            "text": spec.text[:MAX_TEXT],
            "origin": spec.origin,
            "recalled": 0,
            "last_recalled": "",
        },
        related_ids=tuple(dict.fromkeys(spec.related)),
        salience=spec.salience,
    )


def mark_recalled(memory: MemoryRecord, today: dt.date) -> MemoryRecord:
    """The same memory after the host has brought it up again: it fades more slowly."""
    facts = {**memory.facts, "recalled": recalls(memory) + 1, "last_recalled": today.isoformat()}
    return memory.model_copy(update={"facts": facts})


def prune(
    memories: Sequence[MemoryRecord], today: dt.date, cap: int = MEMORY_CAP
) -> tuple[MemoryRecord, ...]:
    """Forget the faintest memories once there are more than ``cap``; the rest keep their order."""
    if len(memories) <= cap:
        return tuple(memories)
    keep = {
        memory.id
        for memory in sorted(memories, key=lambda memory: (-strength(memory, today), memory.id))[
            :cap
        ]
    }
    return tuple(memory for memory in memories if memory.id in keep)
