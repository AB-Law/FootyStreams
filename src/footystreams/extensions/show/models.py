"""Small frozen models shared by the show: segments, screens and the lines the hosts speak."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MIN_LINE_MS = 2_500
MAX_LINE_MS = 60_000
MAX_LINE_CHARS = 360


class ShowModel(BaseModel):
    """Immutable, no-extras base for everything the show stores or publishes."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SegmentKind(StrEnum):
    """What a stretch of the show is."""

    PREVIEW = "preview"
    RECAP = "recap"
    CLUB_HISTORY = "club_history"
    MANAGER_STORY = "manager_story"
    PLAYER_STORY = "player_story"
    BANTER = "banter"
    TABLE_TALK = "table_talk"
    INTERVIEW = "interview"
    BREAK = "break"
    BREAKING = "breaking"


Pick = Literal["home", "draw", "away"]


class ScreenRow(ShowModel):
    """One row on a wall screen: a label and, usually, a value (a score, a points total)."""

    label: str = Field(max_length=60)
    value: str = Field(default="", max_length=20)


class Screen(ShowModel):
    """What the right-hand wall screen shows: a score, a table or a fact card."""

    kind: Literal["score", "table", "card"]
    title: str = Field(max_length=40)
    rows: tuple[ScreenRow, ...] = ()


class SpokenLine(ShowModel):
    """One thing a host says, with how long it holds the screen."""

    speaker_id: str
    speaker_name: str
    text: str = Field(min_length=1, max_length=MAX_LINE_CHARS)
    duration_ms: int = Field(ge=MIN_LINE_MS, le=MAX_LINE_MS)
    uses: tuple[str, ...] = ()


class Slide(ShowModel):
    """One card of a break: a sponsor, the table, the latest results, the next match, a flash."""

    kind: Literal["ad", "table", "results", "fixture", "breaking"]
    title: str = Field(max_length=60)
    lines: tuple[str, ...] = ()
    rows: tuple[ScreenRow, ...] = ()
    accent: str = "#f2c200"
    dark: str = "#101418"
    seconds: float = Field(default=6.0, gt=0)


class GuestRef(ShowModel):
    """A guest on the desk: a real person of the world, drawn from their own appearance and kit."""

    id: str
    name: str
    kind: Literal["player", "manager"]
    role: str = Field(max_length=40)
    appearance: dict[str, str | int]
    kit_primary: str
    kit_secondary: str


class MemoryNote(ShowModel):
    """Something a host remembers, for the page that shows what the desk has in mind."""

    host: str
    kind: str
    text: str


class Segment(ShowModel):
    """A finished stretch of the show, as the viewer plays it.

    A talking segment has ``lines``; a break has ``slides`` and no lines. ``ticker`` and
    ``memories`` are the desk as it stands once the segment has aired (empty for a segment that
    was slotted in later, which shows the previous ones), and ``alert`` is the headline of a
    BREAKING NEWS segment.
    """

    id: str
    number: int = Field(ge=1)
    kind: SegmentKind
    title: str = Field(max_length=80)
    teaser: str = Field(default="", max_length=80)
    label: str = Field(max_length=40)
    lines: tuple[SpokenLine, ...] = ()
    slides: tuple[Slide, ...] = ()
    screen: Screen | None = None
    guest: GuestRef | None = None
    alert: str = ""
    ticker: tuple[str, ...] = ()
    memories: tuple[MemoryNote, ...] = ()
    duration_s: float = Field(gt=0)
    air_at: float = 0.0


class CastMember(ShowModel):
    """A host at the desk: who they are and what they bring (from the world's media crew)."""

    id: str
    name: str
    role: str
    humor: int = Field(ge=0, le=100)
    interview_style: str = ""
    expertise: tuple[str, ...] = ()
    catchphrases: tuple[str, ...] = ()
    birthplace: str = ""
