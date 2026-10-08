"""Match stack: sheets, setup and match record."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.club import ClubColours, Fanbase
from footystreams.domain.manager import Philosophy, SubHabits
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.stadium import Stadium
from footystreams.domain.tactics import TeamTactics
from footystreams.domain.types import (
    Attribute,
    ClubId,
    Competence,
    CompetitionId,
    Duty,
    FixtureId,
    FormationId,
    GameDate,
    ManagerId,
    MatchId,
    PlayerId,
    RefereeId,
    Reputation,
    RoleId,
    SeasonId,
    StadiumId,
    Unit,
)
from footystreams.domain.versions import SIM_VERSION
from footystreams.domain.weather import Weather

XI_SIZE = 11
MAX_BENCH = 9


class MatchStatus(StrEnum):
    """Persisted match status."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"


class LineupSlot(DomainModel):
    """Starting XI slot with assigned role and duty."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "slot": "S",
        "player_id": "S",
        "role": "S",
        "duty": "S",
    }

    slot: int = Field(ge=0, le=10)
    player_id: PlayerId
    role: RoleId
    duty: Duty


class ClubSnapshot(DomainModel):
    """Compact club identity on a sheet."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S",
        "name": "S",
        "short_code": "S",
        "colours": "R",
        "reputation": "S",
        "rivalries_with_opponent": "S",
    }

    id: ClubId
    name: str
    short_code: str
    colours: ClubColours
    reputation: Reputation
    rivalries_with_opponent: Unit = 0.0


class ManagerSnapshot(DomainModel):
    """Compact manager identity on a sheet."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "S",
        "name": "S",
        "philosophy": "S",
        "flexibility": "S",
        "sub_habits": "S",
        "tactical_knowledge": "S",
        "formation_proficiency": "S",
        "fallback_formations": "S",
    }

    id: ManagerId
    name: str
    philosophy: Philosophy
    flexibility: Unit
    sub_habits: SubHabits
    tactical_knowledge: Attribute
    formation_proficiency: Mapping[FormationId, Competence] = Field(default_factory=dict)
    fallback_formations: tuple[FormationId, ...] = ()


class PolicyRef(DomainModel):
    """Which ManagerPolicy built in-match decisions."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "policy_id": "S",
        "policy_version": "S",
    }

    policy_id: str
    policy_version: str


class CornerTakers(DomainModel):
    """Left/right corner taker ids."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"left": "S", "right": "S"}

    left: PlayerId
    right: PlayerId


class TeamSheet(DomainModel):
    """Frozen sim input for one side."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "club": "S",
        "manager": "S",
        "assistant_tactical_input": "S",
        "physio_quality": "S",
        "lineup": "S",
        "bench": "S",
        "squad": "S",
        "tactics": "S",
        "policy": "S",
        "captain_id": "S",
        "penalty_takers": "S",
        "free_kick_takers": "S",
        "corner_takers": "S",
        "fanbase": "S",
        "stadium": "S",
    }

    club: ClubSnapshot
    manager: ManagerSnapshot
    assistant_tactical_input: Attribute = 50
    physio_quality: Attribute = 50
    lineup: tuple[LineupSlot, ...]
    bench: tuple[PlayerId, ...] = ()
    squad: Mapping[PlayerId, PlayerSnapshot]
    tactics: TeamTactics
    policy: PolicyRef
    captain_id: PlayerId
    penalty_takers: tuple[PlayerId, ...] = ()
    free_kick_takers: tuple[PlayerId, ...] = ()
    corner_takers: CornerTakers
    fanbase: Fanbase | None = None
    stadium: Stadium | None = None

    @model_validator(mode="after")
    def _lineup_integrity(self) -> Self:
        if len(self.lineup) != XI_SIZE:
            msg = f"lineup must have {XI_SIZE} slots"
            raise ValueError(msg)
        if len(self.bench) > MAX_BENCH:
            msg = f"bench max {MAX_BENCH}"
            raise ValueError(msg)
        for slot in self.lineup:
            if slot.player_id not in self.squad:
                msg = f"lineup player {slot.player_id} missing from squad"
                raise ValueError(msg)
        for player_id in self.bench:
            if player_id not in self.squad:
                msg = f"bench player {player_id} missing from squad"
                raise ValueError(msg)
        return self


class MatchSetup(DomainModel):
    """Full inputs to simulate_match."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "match_id": "S",
        "fixture_id": "S",
        "home": "S",
        "away": "S",
        "weather": "S",
        "referee_id": "S",
        "attendance": "S",
        "is_derby": "S",
        "importance": "S",
    }

    match_id: MatchId
    fixture_id: FixtureId
    home: TeamSheet
    away: TeamSheet
    weather: Weather
    referee_id: RefereeId
    attendance: int = Field(ge=0)
    is_derby: bool = False
    importance: Unit = 0.5


def players_on_both_sheets(setup: MatchSetup) -> list[PlayerId]:
    """Return the ids of players who appear on both teams' sheets, sorted (empty when sound).

    The one definition of the "no player on both teams" rule (invariant M05); the simulator rejects
    such a setup up front and `verify` reports it on a log.
    """
    return sorted(set(setup.home.squad) & set(setup.away.squad))


class SetupRef(DomainModel):
    """Lightweight identity of the setup used for a MatchResult."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "match_id": "L",
        "home_club_id": "L",
        "away_club_id": "L",
        "fixture_id": "L",
    }

    match_id: MatchId
    home_club_id: ClubId
    away_club_id: ClubId
    fixture_id: FixtureId


class Match(DomainModel):
    """Persisted match record (events live in the events package)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "id": "L",
        "fixture_id": "L",
        "competition_id": "L",
        "season_id": "L",
        "matchday": "L",
        "date": "L",
        "venue_stadium_id": "L",
        "home_club_id": "L",
        "away_club_id": "L",
        "weather": "S",
        "referee_id": "S",
        "attendance": "S",
        "is_derby": "S",
        "importance": "S",
        "home_sheet": "S",
        "away_sheet": "S",
        "seed": "S",
        "config_hash": "S",
        "sim_version": "S",
        "status": "L",
        "home_goals": "L",
        "away_goals": "L",
        "ht_home": "L",
        "ht_away": "L",
        "log_digest": "L",
    }

    id: MatchId
    fixture_id: FixtureId
    competition_id: CompetitionId
    season_id: SeasonId
    matchday: int = Field(ge=1)
    date: GameDate
    venue_stadium_id: StadiumId
    home_club_id: ClubId
    away_club_id: ClubId
    weather: Weather
    referee_id: RefereeId
    attendance: int = Field(ge=0)
    is_derby: bool = False
    importance: Unit = 0.5
    home_sheet: TeamSheet
    away_sheet: TeamSheet
    seed: int
    config_hash: str
    sim_version: str = SIM_VERSION
    status: MatchStatus = MatchStatus.SCHEDULED
    home_goals: int | None = None
    away_goals: int | None = None
    ht_home: int | None = None
    ht_away: int | None = None
    log_digest: str | None = None
