"""Reading what the model sends back, and refusing anything that is not grounded.

The model may phrase the facts; it may not add to them. A reply is rejected, with a reason the
model can act on, if it is not the right shape, has a host that is not at the desk, uses a number
that is not in the facts, or names a person, club or ground the segment does not involve.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from footystreams.extensions.show.memory import LLM_KINDS, MAX_TEXT
from footystreams.extensions.show.models import MAX_LINE_CHARS, Pick, ShowModel
from footystreams.extensions.show.textutil import fold, speakable, strip_thinking, words

MIN_LINE_CHARS = 12
MAX_NEW_MEMORIES = 2
PICKS: tuple[Pick, ...] = ("home", "draw", "away")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


class ReplyError(ValueError):
    """The model's reply cannot be used; the message says why, for the next attempt."""


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """One accepted line: who says it, what they say and which memories they bring up."""

    speaker_id: str
    text: str
    uses: tuple[str, ...]


class MemoryProposal(ShowModel):
    """A memory the model suggests the show keep; it is stored as the model's, not as fact."""

    host_id: str
    kind: str
    text: str


class PickProposal(ShowModel):
    """A host's prediction for the match being previewed."""

    host_id: str
    pick: Pick


@dataclass(frozen=True, slots=True)
class Reply:
    """A reply that passed every check."""

    lines: tuple[ParsedLine, ...]
    memories: tuple[MemoryProposal, ...]
    picks: tuple[PickProposal, ...]


@dataclass(frozen=True, slots=True)
class ReplyRules:
    """What a reply is checked against."""

    hosts: Mapping[str, str]
    memory_ids: frozenset[str]
    allowed_names: frozenset[str]
    vocabulary: tuple[str, ...]
    allowed_numbers: frozenset[str]
    min_lines: int
    max_lines: int
    ask_predictions: bool
    recent: frozenset[str] = frozenset()
    must_speak: frozenset[str] = frozenset()


def numbers_in(text: str) -> set[str]:
    """The numbers in ``text`` with thousands separators removed: ``27,500`` is ``27500``."""
    return {found.replace(",", "") for found in _NUMBER.findall(text)}


def names_in(text: str, vocabulary: Iterable[str]) -> set[str]:
    """The world names that appear in ``text``, matched without regard to accents."""
    plain = fold(text)
    return {name for name in vocabulary if re.search(rf"\b{re.escape(fold(name))}\b", plain)}


def _load(raw: str) -> dict[str, object]:
    text = strip_thinking(raw)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        msg = "the reply is not a JSON object"
        raise ReplyError(msg)
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        msg = f"the reply is not valid JSON ({error.msg} at character {error.pos})"
        raise ReplyError(msg) from error
    if not isinstance(data, dict):
        msg = "the reply is not a JSON object"
        raise ReplyError(msg)
    return data


def _part_of(name: str, allowed: set[str]) -> bool:
    """Whether ``name`` is allowed, or a whole-word piece of an allowed name."""
    return any(re.search(rf"\b{re.escape(name)}\b", full) for full in allowed)


def _grounded(text: str, where: str, rules: ReplyRules) -> None:
    stray = numbers_in(text) - rules.allowed_numbers
    if stray:
        msg = f"{where} uses the number {sorted(stray)[0]}, which is not in the facts"
        raise ReplyError(msg)
    allowed = {fold(name) for name in rules.allowed_names}
    named = [name for name in names_in(text, rules.vocabulary) if not _part_of(fold(name), allowed)]
    if named:
        msg = f"{where} names {sorted(named)[0]}, who is not part of this segment"
        raise ReplyError(msg)


def _host(value: object, rules: ReplyRules, where: str) -> str:
    key = str(value or "")
    if key in rules.hosts.values():
        return key
    if key in rules.hosts:
        return rules.hosts[key]
    msg = f"{where} has speaker {key!r}, who is not at the desk"
    raise ReplyError(msg)


def _line(row: object, number: int, rules: ReplyRules) -> ParsedLine:
    where = f"line {number}"
    if not isinstance(row, dict):
        msg = f"{where} is not an object"
        raise ReplyError(msg)
    text = speakable(str(row.get("text") or ""))
    if len(text) < MIN_LINE_CHARS or len(text) > MAX_LINE_CHARS:
        msg = f"{where} has {len(text)} characters; lines need {MIN_LINE_CHARS} to {MAX_LINE_CHARS}"
        raise ReplyError(msg)
    if words(text) in rules.recent:
        msg = f"{where} repeats something that has already been on air; say something new"
        raise ReplyError(msg)
    _grounded(text, where, rules)
    used = row.get("uses") or []
    uses = (
        tuple(str(item) for item in used if str(item) in rules.memory_ids)
        if isinstance(used, list)
        else ()
    )
    return ParsedLine(_host(row.get("speaker_id"), rules, where), text, uses)


def _lines(data: dict[str, object], rules: ReplyRules) -> tuple[ParsedLine, ...]:
    rows = data.get("lines")
    if not isinstance(rows, list):
        msg = 'the reply has no "lines" list'
        raise ReplyError(msg)
    lines = tuple(
        _line(row, number, rules) for number, row in enumerate(rows[: rules.max_lines], start=1)
    )
    if len(lines) < rules.min_lines:
        msg = f"only {len(lines)} lines; write at least {rules.min_lines}"
        raise ReplyError(msg)
    if len({words(line.text) for line in lines}) < len(lines):
        msg = "a line is repeated within the reply"
        raise ReplyError(msg)
    if len({line.speaker_id for line in lines}) < 2:  # noqa: PLR2004 - a conversation needs two voices
        msg = "one host spoke every line; the hosts must talk to each other"
        raise ReplyError(msg)
    silent = rules.must_speak - {line.speaker_id for line in lines}
    if silent:
        msg = f"{sorted(silent)} must speak too; the guest has to answer"
        raise ReplyError(msg)
    return lines


def _memories(data: dict[str, object], rules: ReplyRules) -> tuple[MemoryProposal, ...]:
    rows = data.get("memories")
    kept: list[MemoryProposal] = []
    for row in rows[:MAX_NEW_MEMORIES] if isinstance(rows, list) else []:
        if not isinstance(row, dict) or str(row.get("kind")) not in LLM_KINDS:
            continue
        text = speakable(str(row.get("text") or ""))[:MAX_TEXT]
        if len(text) < MIN_LINE_CHARS:
            continue
        _grounded(text, "a new memory", rules)
        kept.append(
            MemoryProposal(
                host_id=_host(row.get("host_id"), rules, "a new memory"),
                kind=str(row["kind"]),
                text=text,
            )
        )
    return tuple(kept)


def _picks(data: dict[str, object], rules: ReplyRules) -> tuple[PickProposal, ...]:
    if not rules.ask_predictions:
        return ()
    rows = data.get("predictions")
    chosen: dict[str, PickProposal] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("pick") in PICKS:
            host = _host(row.get("host_id"), rules, "a prediction")
            chosen.setdefault(host, PickProposal(host_id=host, pick=row["pick"]))
    missing = set(rules.hosts.values()) - set(chosen)
    if missing:
        msg = f'"predictions" needs a pick for every host; missing {sorted(missing)}'
        raise ReplyError(msg)
    return tuple(chosen.values())


def parse_reply(raw: str, rules: ReplyRules) -> Reply:
    """Parse and check a model reply, or raise ``ReplyError`` saying what to fix."""
    data = _load(raw)
    return Reply(_lines(data, rules), _memories(data, rules), _picks(data, rules))
