"""Match summary models and the match_summary event."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import PlayerId, Unit
from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION
from footystreams.events.base import EventBase, event_usage
from footystreams.events.context import EventContext
from footystreams.events.summary_rows import (
    Hook,
    InjuryReport,
    KeyMoment,
    MomentumPoint,
    PassLink,
    ShotPoint,
    XgPoint,
    ZoneFlow,
)


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
        "key_passes": "L",
        "dribbles": "L",
        "dribbles_won": "L",
        "tackles": "L",
        "tackles_won": "L",
        "interceptions": "L",
        "clearances": "L",
        "offsides": "L",
        "saves": "L",
        "big_chances": "L",
        "xt": "L",
        "field_tilt": "L",
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
    key_passes: int = Field(ge=0, default=0)
    dribbles: int = Field(ge=0, default=0)
    dribbles_won: int = Field(ge=0, default=0)
    tackles: int = Field(ge=0, default=0)
    tackles_won: int = Field(ge=0, default=0)
    interceptions: int = Field(ge=0, default=0)
    clearances: int = Field(ge=0, default=0)
    offsides: int = Field(ge=0, default=0)
    saves: int = Field(ge=0, default=0)
    big_chances: int = Field(ge=0, default=0)
    xt: float = 0.0  # total threat gained by completed passes
    field_tilt: Unit = 0.5  # share of final-third passes made by this side


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
        "starts": "L",
        "position": "L",
        "shots_on_target": "L",
        "xa": "L",
        "xt": "L",
        "passes": "L",
        "passes_completed": "L",
        "key_passes": "L",
        "progressive_passes": "L",
        "dribbles": "L",
        "dribbles_won": "L",
        "tackles": "L",
        "tackles_won": "L",
        "interceptions": "L",
        "clearances": "L",
        "fouls": "L",
        "fouled": "L",
        "saves": "L",
        "goals_conceded": "L",
        "clean_sheet": "L",
        "end_exhaustion": "L",
        "injured": "L",
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
    starts: bool = True
    position: str = ""
    shots_on_target: int = Field(ge=0, default=0)
    xa: float = Field(ge=0.0, default=0.0)
    xt: float = 0.0
    passes: int = Field(ge=0, default=0)
    passes_completed: int = Field(ge=0, default=0)
    key_passes: int = Field(ge=0, default=0)
    progressive_passes: int = Field(ge=0, default=0)
    dribbles: int = Field(ge=0, default=0)
    dribbles_won: int = Field(ge=0, default=0)
    tackles: int = Field(ge=0, default=0)
    tackles_won: int = Field(ge=0, default=0)
    interceptions: int = Field(ge=0, default=0)
    clearances: int = Field(ge=0, default=0)
    fouls: int = Field(ge=0, default=0)
    fouled: int = Field(ge=0, default=0)
    saves: int = Field(ge=0, default=0)
    goals_conceded: int = Field(ge=0, default=0)
    clean_sheet: bool = False
    end_exhaustion: Unit = 0.0
    injured: bool = False


class PlayerRating(DomainModel):
    """Post-match 3-10 rating row."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "player_id": "L",
        "rating": "L",
        "breakdown": "L",
    }

    player_id: PlayerId
    rating: float = Field(ge=3.0, le=10.0)
    breakdown: Mapping[str, float] = Field(default_factory=dict)


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
        "injuries": "L",
        "momentum_timeline": "L",
        "xg_timeline": "L",
        "key_moments": "L",
        "hooks": "L",
        "pass_matrix": "L",
        "zone_pass_flow": "L",
        "shot_map": "L",
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
    injuries: tuple[InjuryReport, ...] = ()
    momentum_timeline: tuple[MomentumPoint, ...] = ()
    xg_timeline: tuple[XgPoint, ...] = ()
    key_moments: tuple[KeyMoment, ...] = ()
    hooks: tuple[Hook, ...] = ()
    pass_matrix: tuple[PassLink, ...] = ()
    zone_pass_flow: tuple[ZoneFlow, ...] = ()
    shot_map: tuple[ShotPoint, ...] = ()


class MatchSummaryEvent(EventBase):
    """Final event carrying the MatchSummary payload."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = event_usage(ctx="S", summary="L")

    type: Literal["match_summary"] = "match_summary"
    ctx: EventContext = Field(default_factory=EventContext)
    summary: MatchSummary
