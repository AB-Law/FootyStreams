"""What the model is told about one stretch of the show: a goal, the facts and who may be named."""

from __future__ import annotations

from pydantic import Field, JsonValue

from footystreams.extensions.show.bible import Result
from footystreams.extensions.show.models import GuestRef, Screen, ShowModel


class SegmentBrief(ShowModel):
    """The ground truth for one segment. Hosts may phrase it; they may not add to it."""

    title: str = Field(max_length=80)
    # What the schedule says before it airs: the title, unless the title gives the result away.
    teaser: str = Field(default="", max_length=80)
    label: str = Field(max_length=40)
    goal: str
    facts: dict[str, JsonValue]
    names: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    screen: Screen | None = None
    ask_predictions: bool = False
    result: Result | None = None
    guest: GuestRef | None = None
    alert: str = ""
