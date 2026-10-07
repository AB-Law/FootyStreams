"""Competition, season and match rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import ClubId, CompetitionId, GameDate, SeasonId

DEFAULT_CLUBS = 8
DEFAULT_MATCHDAYS = 14
DEFAULT_SUBS = 5
DEFAULT_SUB_WINDOWS = 3
DEFAULT_BENCH = 9
DEFAULT_MATCH_MINUTES = 90


class MatchRules(DomainModel):
    """Competition match regulations."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "subs_max": "S",
        "sub_windows": "S",
        "bench_size": "S",
        "match_minutes": "S",
        "extra_time": "S",
        "penalties": "S",
        "video_review": "S",
    }

    subs_max: int = Field(ge=0, le=7, default=DEFAULT_SUBS)
    sub_windows: int = Field(ge=0, le=5, default=DEFAULT_SUB_WINDOWS)
    bench_size: int = Field(ge=0, le=12, default=DEFAULT_BENCH)
    match_minutes: int = Field(ge=1, default=DEFAULT_MATCH_MINUTES)
    extra_time: bool = False
    penalties: bool = False
    video_review: bool = False


class Competition(DomainModel):
    """A league or cup competition."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "name": "L",
        "short_name": "L",
        "club_ids": "L",
        "rules": "S",
    }

    id: CompetitionId
    name: str = Field(min_length=1, max_length=80)
    short_name: str = Field(min_length=1, max_length=40)
    club_ids: tuple[ClubId, ...]
    rules: MatchRules = Field(default_factory=MatchRules)


class Season(DomainModel):
    """One season of a competition."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "competition_id": "L",
        "label": "L",
        "starts_on": "L",
        "ends_on": "L",
        "matchdays": "L",
    }

    id: SeasonId
    competition_id: CompetitionId
    label: str = Field(min_length=1, max_length=40)
    starts_on: GameDate
    ends_on: GameDate
    matchdays: int = Field(ge=1, default=DEFAULT_MATCHDAYS)
