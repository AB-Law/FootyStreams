"""The prompt: who the hosts are, what they remember, the facts of the segment and the rules."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.memory import MemoryRecord
from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.memory import retrieve, text_of
from footystreams.extensions.show.models import CastMember
from footystreams.extensions.show.segment_brief import SegmentBrief

MEMORIES_PER_HOST = 3
CATCHPHRASE_COOLDOWN = 8
MIN_LINES = 7
MAX_LINES = 10

SYSTEM_PROMPT = (
    "You write the live dialogue for VPL News, a 24/7 television desk show about the Valmere "
    "Premier League, a fictional football league. Three hosts sit at the desk. They have worked "
    "together for years: they tease each other, disagree, finish each other's thoughts and "
    "remember things.\n\n"
    "Rules:\n"
    '1. Facts. Use only the names, numbers, results and history in "facts" and in the hosts\' '
    '"memories". Never invent clubs, players, scores, statistics, dates or events, and never use '
    "a number that is not in the facts. If you do not have a fact, leave it out.\n"
    "2. Voice. Each host speaks in character: their humor, interview style, expertise and "
    "catchphrases (a catchphrase only if it is listed as available, at most once in the segment). "
    "Jokes come from the facts and from the hosts' memories: callbacks to a running joke, an old "
    "opinion or a missed prediction land best. Never explain a joke. Sometimes a person with "
    'the role "guest" is on the desk: a visitor, not one of the hosts. They answer in the first '
    "person, as themselves, in the manner their personality suggests, and only about what the "
    "facts say. Hosts never speak for them.\n"
    "3. Speech. Plain spoken sentences, one to three per line, each line under 300 characters. "
    "React to the previous line. No lists, stage directions, emoji, hashtags or markdown. Spell "
    "names exactly as given. Write every number as digits (1871, 27,500, 2-1), never in words. "
    'Never repeat or quote anything in "just_said": it has already been on air. Do not greet '
    "viewers or say goodbye: the show carries on.\n"
    '4. Memory. A host may bring up one of their own memories by putting its id in "uses". Every '
    'segment should also add one or two NEW memories in "memories": this is how the desk builds '
    "its history. A running joke that has just started, an opinion a host has taken, something "
    "personal a host has admitted. They must stay consistent with the facts.\n"
    "5. Reply with JSON only and nothing else: "
    '{"lines":[{"speaker_id":"...","text":"...","uses":["memory id"]}],'
    '"memories":[{"host_id":"...","kind":"running_joke|opinion|anecdote","text":"..."}],'
    '"predictions":[{"host_id":"...","pick":"home|draw|away"}]}. '
    '"predictions" only when the segment asks for them, and then one for every host.'
)


@dataclass(frozen=True, slots=True)
class Prompt:
    """The two messages to send and the memory ids a reply may legitimately point at."""

    system: str
    user: str
    memory_ids: frozenset[str]


def available_catchphrases(host: CastMember, bible: ShowBible) -> list[str]:
    """The host's catchphrases they have not used lately."""
    return [
        phrase
        for phrase in host.catchphrases
        if bible.segment_count
        - bible.catchphrase_uses.get(f"{host.id}|{phrase}", -CATCHPHRASE_COOLDOWN)
        >= CATCHPHRASE_COOLDOWN
    ]


def _memory_card(memory: MemoryRecord) -> dict[str, str]:
    return {"id": memory.id, "kind": memory.kind, "text": text_of(memory)}


def host_card(
    host: CastMember, bible: ShowBible, memories: Sequence[MemoryRecord]
) -> dict[str, object]:
    """Everything the model needs to play one host."""
    return {
        "id": host.id,
        "name": host.name,
        "role": host.role,
        "humor_0_to_100": host.humor,
        "interview_style": host.interview_style,
        "expertise": list(host.expertise),
        "from": host.birthplace,
        "catchphrases_available": available_catchphrases(host, bible),
        "memories": [_memory_card(memory) for memory in memories],
    }


def build_prompt(brief: SegmentBrief, cast: Sequence[CastMember], bible: ShowBible) -> Prompt:
    """The prompt for one segment."""
    topics = frozenset(brief.topics)
    cards: list[dict[str, object]] = []
    given: set[str] = set()
    for host in cast:
        recalled = retrieve(bible.memories, host.id, topics, bible.today, MEMORIES_PER_HOST)
        given.update(memory.id for memory in recalled)
        cards.append(host_card(host, bible, recalled))
    payload = {
        "segment": {
            "title": brief.title,
            "goal": brief.goal,
            "asks_for_predictions": brief.ask_predictions,
        },
        "facts": brief.facts,
        "hosts": cards,
        "just_said": list(bible.last_lines),
        "length": f"{MIN_LINES} to {MAX_LINES} lines, at least two different hosts",
    }
    return Prompt(SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False), frozenset(given))
