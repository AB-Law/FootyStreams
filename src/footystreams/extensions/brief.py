"""Structured facts for a news-desk or studio segment (ground truth only; no invented lore)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Beat = Literal["intro", "club_colour", "player_focus", "wrap"]


class CareerLine(BaseModel):
    """One speakable career stint (prior club name resolved when known)."""

    club_name: str | None
    from_year: int
    to_year: int
    detail: str


class PersonBrief(BaseModel):
    """A player or manager the desk may talk about."""

    id: str
    known_as: str
    role: str
    side: Literal["home", "away"]
    age: int | None = None
    career: tuple[CareerLine, ...] = ()
    storyline_keys: tuple[str, ...] = ()


class ClubBrief(BaseModel):
    """Club identity the desk may cite."""

    id: str
    name: str
    nickname: str
    short_code: str
    founded_year: int
    city: str
    rivalry_label: str = ""
    rivalry_origin: str = ""


class ManagerBrief(BaseModel):
    """Manager colour for the desk."""

    id: str
    known_as: str
    side: Literal["home", "away"]
    style: str
    press_tone: str
    career: tuple[CareerLine, ...] = ()


class RelationshipBrief(BaseModel):
    """A public relationship touching people in the brief."""

    kind: str
    a_name: str
    b_name: str
    strength: float


class NewsItem(BaseModel):
    """A public WorldEvent fact, already filtered for visibility."""

    kind: str
    date: str
    summary: str


class ScoreBrief(BaseModel):
    """Final (or current) scoreline and half-time."""

    home: int
    away: int
    ht_home: int = 0
    ht_away: int = 0
    potm_name: str | None = None


class CrewMember(BaseModel):
    """On-air talent available for the segment."""

    id: str
    known_as: str
    role: str
    catchphrases: tuple[str, ...] = ()
    expertise_tags: tuple[str, ...] = ()


class BroadcastBrief(BaseModel):
    """Everything a facts-only narrator may use for one match desk segment."""

    match_id: str
    home: ClubBrief
    away: ClubBrief
    home_manager: ManagerBrief | None = None
    away_manager: ManagerBrief | None = None
    players: tuple[PersonBrief, ...] = ()
    relationships: tuple[RelationshipBrief, ...] = ()
    news: tuple[NewsItem, ...] = ()
    score: ScoreBrief | None = None
    hooks: tuple[str, ...] = ()
    key_moments: tuple[str, ...] = ()
    crew: tuple[CrewMember, ...] = ()
    team_stats_note: str = ""


class CommentaryLine(BaseModel):
    """One spoken line for the studio scene."""

    speaker_id: str
    speaker_name: str
    text: str = Field(min_length=1, max_length=700)
    beat: Beat
    duration_ms: int = Field(ge=500, le=60_000, default=12_000)
