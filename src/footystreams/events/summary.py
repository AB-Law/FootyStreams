"""Match summary models and the match_summary event."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import PlayerId, Unit
from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION
from footystreams.events.base import EventBase
from footystreams.events.context import EventContext


class TeamStats(DomainModel):
    """Aggregate team stats for one side."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "possession": "L",
        "shots": "L",
        "shots_on_target": "L",
        "xg": "L",
        "passes": "L",
        "pass_accuracy": "L",
        "fouls": "L",
        "corners": "L",
        "yellows": "L",
        "reds": "L",
    }

    possession: Unit = 0.5
    shots: int = Field(ge=0, default=0)
    shots_on_target: int = Field(ge=0, default=0)
    xg: float = Field(ge=0.0, default=0.0)
    passes: int = Field(ge=0, default=0)
    pass_accuracy: Unit = 0.0
    fouls: int = Field(ge=0, default=0)
    corners: int = Field(ge=0, default=0)
    yellows: int = Field(ge=0, default=0)
    reds: int = Field(ge=0, default=0)


class PlayerMatchStats(DomainModel):
    """Per-player match stats folded into season totals later."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "player_id": "L",
        "minutes": "L",
        "goals": "L",
        "assists": "L",
        "shots": "L",
        "xg": "L",
        "yellows": "L",
        "reds": "L",
        "rating": "L",
    }

    player_id: PlayerId
    minutes: int = Field(ge=0, default=0)
    goals: int = Field(ge=0, default=0)
    assists: int = Field(ge=0, default=0)
    shots: int = Field(ge=0, default=0)
    xg: float = Field(ge=0.0, default=0.0)
    yellows: int = Field(ge=0, default=0)
    reds: int = Field(ge=0, default=0)
    rating: float = Field(ge=3.0, le=10.0, default=6.0)


class PlayerRating(DomainModel):
    """Post-match 3-10 rating row."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "player_id": "L",
        "rating": "L",
    }

    player_id: PlayerId
    rating: float = Field(ge=3.0, le=10.0)


class MatchSummary(DomainModel):
    """Full match summary document."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "schema_version": "L",
        "sim_version": "L",
        "config_hash": "L",
        "seed": "L",
        "log_digest": "L",
        "score_home": "L",
        "score_away": "L",
        "ht_home": "L",
        "ht_away": "L",
        "attendance": "L",
        "duration_s": "L",
        "team_stats_home": "L",
        "team_stats_away": "L",
        "player_stats": "L",
        "ratings": "L",
        "player_of_the_match": "L",
    }

    schema_version: str = SCHEMA_VERSION
    sim_version: str = SIM_VERSION
    config_hash: str
    seed: int
    log_digest: str
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)
    ht_home: int = Field(ge=0, default=0)
    ht_away: int = Field(ge=0, default=0)
    attendance: int = Field(ge=0, default=0)
    duration_s: int = Field(ge=0, default=0)
    team_stats_home: TeamStats = Field(default_factory=TeamStats)
    team_stats_away: TeamStats = Field(default_factory=TeamStats)
    player_stats: tuple[PlayerMatchStats, ...] = ()
    ratings: tuple[PlayerRating, ...] = ()
    player_of_the_match: PlayerId | None = None


class MatchSummaryEvent(EventBase):
    """Final event carrying the MatchSummary payload."""

    type: Literal["match_summary"] = "match_summary"
    ctx: EventContext = Field(default_factory=EventContext)
    summary: MatchSummary
