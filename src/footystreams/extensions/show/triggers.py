"""Triggers: things someone outside the show asks for, as small JSON files the producer picks up.

``breaking`` puts a BREAKING NEWS headline on air at once; ``guest`` asks for a person of the world
(by name or id) to be interviewed next.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import Field, ValidationError

from footystreams.extensions.show.models import ShowModel
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.textutil import words

MAX_TEXT = 140


class Trigger(ShowModel):
    """One request: a kind and its text (a headline, or the name of a guest)."""

    kind: Literal["breaking", "guest"]
    text: str = Field(min_length=1, max_length=MAX_TEXT)


def parse_trigger(raw: str) -> Trigger:
    """Read a trigger file's text, or raise ``ValueError`` saying what is wrong with it."""
    try:
        return Trigger.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as error:
        msg = f"not a trigger: {error}"
        raise ValueError(msg) from error


def resolve_guest(room: Newsroom, who: str) -> str | None:
    """The id of the person ``who`` names (an id, a name or its start), if there is one."""
    wanted = words(who)
    if not wanted:
        return None
    people = {**room.managers, **room.players}
    if who in people:
        return who
    named = {person_id: words(person.known_as) for person_id, person in sorted(people.items())}
    exact = [person_id for person_id, name in named.items() if name == wanted]
    partial = [person_id for person_id, name in named.items() if name.startswith(wanted)]
    found = exact or partial
    return found[0] if found else None
