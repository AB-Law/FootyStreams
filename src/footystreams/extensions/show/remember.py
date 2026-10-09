"""What the desk keeps after a segment airs: results, predictions, memories and catchphrases."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.extensions.show.bible import (
    LAST_LINES_KEPT,
    SEASONS_KEPT,
    Prediction,
    Result,
    ShowBible,
)
from footystreams.extensions.show.ledger import scoreline
from footystreams.extensions.show.memory import (
    MemorySpec,
    make_memory,
    mark_recalled,
    prune,
    slug,
)
from footystreams.extensions.show.models import CastMember, Segment
from footystreams.extensions.show.plan import Plan, Roster, advance
from footystreams.extensions.show.reply import Reply
from footystreams.extensions.show.segment_brief import SegmentBrief

LLM_SALIENCE = {"running_joke": 0.6, "opinion": 0.5, "anecdote": 0.5}
BIG_MARGIN = 3
WRONG_PICK_SALIENCE = 0.7
RIGHT_PICK_SALIENCE = 0.4
MOMENT_SALIENCE = 0.5
BIG_RESULT_SALIENCE = 0.8
INTERVIEW_SALIENCE = 0.6
BREAKING_SALIENCE = 0.7


@dataclass(frozen=True, slots=True)
class Aired:
    """Everything that went into a segment, so the bible can be updated from it."""

    plan: Plan
    brief: SegmentBrief
    reply: Reply
    segment: Segment
    cast: Sequence[CastMember]
    roster: Roster
    guest: CastMember | None = None


def _with_memories(bible: ShowBible, specs: Sequence[MemorySpec]) -> ShowBible:
    """Add memories; one that is already known is brought to mind again instead of duplicated."""
    memories = list(bible.memories)
    number = bible.next_memory
    for spec in specs:
        key = f"{spec.kind}:{slug(spec.text)}"
        known = next((i for i, m in enumerate(memories) if m.summary_key == key), None)
        if known is not None:
            memories[known] = mark_recalled(memories[known], bible.today)
            continue
        memories.append(make_memory(number, bible.today, spec))
        number += 1
    return bible.model_copy(update={"memories": tuple(memories), "next_memory": number})


def _recalled(bible: ShowBible, ids: set[str]) -> ShowBible:
    memories = tuple(mark_recalled(m, bible.today) if m.id in ids else m for m in bible.memories)
    return bible.model_copy(update={"memories": memories})


def _book_result(bible: ShowBible, result: Result | None) -> ShowBible:
    if result is None:
        return bible
    results = (*bible.results, result)
    kept = tuple(r for r in results if r.season > result.season - SEASONS_KEPT)
    return bible.model_copy(update={"results": kept, "date": result.date})


def _others(cast: Sequence[CastMember], host_id: str) -> list[str]:
    return [member.id for member in cast if member.id != host_id]


def _result_memories(
    brief: SegmentBrief, result: Result | None, cast: Sequence[CastMember]
) -> list[MemorySpec]:
    if result is None or not cast:
        return []
    margin = abs(result.home_goals - result.away_goals)
    text = f"{scoreline(result)} on matchday {result.matchday} of season {result.season}"
    host = cast[0].id
    moment = MemorySpec(
        host_id=host,
        kind="match_moment",
        text=text,
        related=[*_others(cast, host), *brief.topics],
        salience=BIG_RESULT_SALIENCE if margin >= BIG_MARGIN else MOMENT_SALIENCE,
    )
    return [moment]


def _settle(bible: ShowBible, result: Result | None, cast: Sequence[CastMember]) -> ShowBible:
    """Turn the picks for a played fixture into memories, and take them off the board."""
    if result is None:
        return bible
    specs: list[MemorySpec] = []
    wording = {"home": result.home_name, "away": result.away_name, "draw": "a draw"}
    for pick in (p for p in bible.predictions if p.fixture_key == result.fixture_key):
        right = pick.pick == result.outcome()
        text = (
            f"{pick.host_name} picked {wording[pick.pick]} for {scoreline(result)} and "
            f"{'was right' if right else 'was wrong'}"
        )
        specs.append(
            MemorySpec(
                host_id=pick.host_id,
                kind="prediction_result",
                text=text,
                related=[*_others(cast, pick.host_id), result.home_id, result.away_id],
                salience=RIGHT_PICK_SALIENCE if right else WRONG_PICK_SALIENCE,
            )
        )
    remaining = tuple(p for p in bible.predictions if p.fixture_key != result.fixture_key)
    return _with_memories(bible.model_copy(update={"predictions": remaining}), specs)


def _add_picks(bible: ShowBible, aired: Aired) -> ShowBible:
    if not aired.brief.ask_predictions:
        return bible
    key = f"s{aired.plan.season}-f{aired.plan.fixture().index:03d}"
    names = {member.id: member.name for member in aired.cast}
    picks = tuple(
        Prediction(fixture_key=key, host_id=p.host_id, host_name=names[p.host_id], pick=p.pick)
        for p in aired.reply.picks
        if p.host_id in names
    )
    return bible.model_copy(update={"predictions": (*bible.predictions, *picks)})


def _proposed(bible: ShowBible, aired: Aired) -> ShowBible:
    everyone = [member.id for member in aired.cast]
    specs = [
        MemorySpec(
            host_id=proposal.host_id,
            kind=proposal.kind,
            text=proposal.text,
            related=[*everyone, *aired.brief.topics]
            if proposal.kind == "running_joke"
            else list(aired.brief.topics),
            salience=LLM_SALIENCE[proposal.kind],
            origin="llm",
        )
        for proposal in aired.reply.memories
        if proposal.host_id in everyone
    ]
    return _with_memories(bible, specs)


def _catchphrases(bible: ShowBible, aired: Aired) -> ShowBible:
    uses = dict(bible.catchphrase_uses)
    by_id = {member.id: member for member in aired.cast}
    for line in aired.reply.lines:
        member = by_id.get(line.speaker_id)
        for phrase in member.catchphrases if member else ():
            if phrase.lower().rstrip(".!") in line.text.lower():
                uses[f"{member.id if member else ''}|{phrase}"] = aired.plan.number
    return bible.model_copy(update={"catchphrase_uses": uses})


def _last_lines(bible: ShowBible, aired: Aired) -> ShowBible:
    spoken = [f"{line.speaker_name}: {line.text}" for line in aired.segment.lines]
    return bible.model_copy(update={"last_lines": tuple(spoken[-LAST_LINES_KEPT:])})


def _occasion(aired: Aired) -> list[MemorySpec]:
    """The interview that was given or the news that broke, as something the presenter remembers."""
    if not aired.cast:
        return []
    host, others = aired.cast[0].id, _others(aired.cast, aired.cast[0].id)
    if aired.guest is not None:
        guest = aired.brief.guest
        role = f" ({guest.role})" if guest else ""
        text = f"{aired.guest.name}{role} sat down on the desk for an interview"
        related = [*others, aired.guest.id, *aired.brief.topics]
        return [MemorySpec(host, "interview", text, related, INTERVIEW_SALIENCE)]
    if aired.brief.alert:
        text = f"Breaking news: {aired.brief.alert}"
        return [MemorySpec(host, "breaking", text, others, BREAKING_SALIENCE)]
    return []


def aired_segment(bible: ShowBible, aired: Aired) -> ShowBible:
    """The bible after ``aired`` has gone out: every memory, result and pick it produced."""
    used = {memory_id for line in aired.reply.lines for memory_id in line.uses}
    result = aired.brief.result
    updated = _recalled(bible, used)
    updated = _book_result(updated, result)
    updated = _with_memories(updated, _result_memories(aired.brief, result, aired.cast))
    updated = _with_memories(updated, _occasion(aired))
    updated = _settle(updated, result, aired.cast)
    updated = _add_picks(updated, aired)
    updated = _proposed(updated, aired)
    updated = _catchphrases(updated, aired)
    updated = _last_lines(updated, aired)
    updated = advance(updated, aired.plan, aired.roster)
    return updated.model_copy(update={"memories": prune(updated.memories, updated.today)})
