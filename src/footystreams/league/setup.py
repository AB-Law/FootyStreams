"""Build the frozen ``MatchSetup`` for a fixture: lineups, snapshots with resolved mood, context."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.fixture import Fixture
from footystreams.domain.manager import Manager
from footystreams.domain.match import ClubSnapshot, MatchSetup, PolicyRef, TeamSheet
from footystreams.domain.mood import StateModifier
from footystreams.domain.player import Player
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.staff import StaffMember, StaffRole
from footystreams.domain.static_tables import FormationCatalog
from footystreams.domain.types import ClubId, MatchId, PlayerId, RefereeId
from footystreams.domain.weather import Weather
from footystreams.league.config import RecoveryConfig
from footystreams.league.lineup_ai import SelectionTables, player_id, select_squad
from footystreams.league.mood import active_modifiers, resolve_mood
from footystreams.league.mood_config import MoodConfig
from footystreams.league.snapshots import snapshot_manager, snapshot_player

POLICY = PolicyRef(policy_id="rules", policy_version="v1")
DEFAULT_STAFF_SKILL = 50
DERBY_IMPORTANCE = 0.8
NORMAL_IMPORTANCE = 0.5


@dataclass(frozen=True, slots=True)
class TeamInputs:
    """Everything the league knows about one side on matchday."""

    club: Club
    manager: Manager
    staff: Sequence[StaffMember]
    squad: Sequence[Player]
    modifiers: Mapping[str, Sequence[StateModifier]]  # by player id


@dataclass(frozen=True, slots=True)
class MatchContext:
    """The fixture and what is decided for it before kick-off."""

    fixture: Fixture
    weather: Weather
    referee_id: RefereeId
    attendance: int
    today: dt.date


@dataclass(frozen=True, slots=True)
class SetupTables:
    """Static tables the build reads."""

    roles: RoleCatalog
    formations: FormationCatalog
    mood: MoodConfig
    recovery: RecoveryConfig


def match_id_for(fixture: Fixture) -> MatchId:
    """The match played for a fixture (``fix_x`` -> ``mch_x``)."""
    return MatchId("mch_" + fixture.id.removeprefix("fix_"))


def _staff_skill(staff: Sequence[StaffMember], role: StaffRole, field: str) -> int:
    members = sorted((m for m in staff if m.role is role), key=lambda member: member.id)
    return int(getattr(members[0].attrs, field)) if members else DEFAULT_STAFF_SKILL


def _rivalry(club: Club, opponent: ClubId) -> float:
    return max((r.intensity for r in club.rivalries if r.club_id == opponent), default=0.0)


def _snapshots(
    team: TeamInputs, picked: Sequence[PlayerId], today: dt.date, mood: MoodConfig
) -> dict[PlayerId, PlayerSnapshot]:
    by_id = {player_id(p): p for p in team.squad}
    result: dict[PlayerId, PlayerSnapshot] = {}
    for pid in picked:
        player = by_id[pid]
        live = active_modifiers(team.modifiers.get(player.id, ()), today)
        result[pid] = snapshot_player(
            player, resolve_mood(player.personality, today, live, mood), today
        )
    return result


def build_team_sheet(
    team: TeamInputs, opponent: ClubId, context: MatchContext, tables: SetupTables
) -> TeamSheet:
    """The sheet for one side: selection, snapshots, takers and the club and manager identity."""
    tactics = team.club.default_tactics
    selection = select_squad(
        team.squad,
        tables.formations.formations[tactics.formation],
        tactics,
        (context.today, SelectionTables(tables.roles, tables.recovery)),
    )
    picked = [slot.player_id for slot in selection.lineup] + list(selection.bench)
    club = team.club
    return TeamSheet(
        club=ClubSnapshot(
            id=club.id,
            name=club.name,
            short_code=club.short_code,
            colours=club.colours,
            reputation=club.club_reputation,
            rivalries_with_opponent=_rivalry(club, opponent),
        ),
        manager=snapshot_manager(team.manager),
        assistant_tactical_input=_staff_skill(
            team.staff, StaffRole.ASSISTANT_MANAGER, "tactical_input"
        ),
        physio_quality=_staff_skill(team.staff, StaffRole.PHYSIO, "injury_treatment"),
        lineup=selection.lineup,
        bench=selection.bench,
        squad=_snapshots(team, picked, context.today, tables.mood),
        tactics=tactics,
        policy=POLICY,
        captain_id=selection.captain,
        penalty_takers=selection.penalty_takers,
        free_kick_takers=selection.free_kick_takers,
        corner_takers=selection.corner_takers,
        fanbase=club.fanbase,
        stadium=club.stadium,
    )


def build_match_setup(
    sides: tuple[TeamInputs, TeamInputs], context: MatchContext, tables: SetupTables
) -> MatchSetup:
    """The full, frozen input of one match; ``sides`` is (home, away)."""
    home, away = sides
    return MatchSetup(
        match_id=match_id_for(context.fixture),
        fixture_id=context.fixture.id,
        home=build_team_sheet(home, away.club.id, context, tables),
        away=build_team_sheet(away, home.club.id, context, tables),
        weather=context.weather,
        referee_id=context.referee_id,
        attendance=context.attendance,
        is_derby=context.fixture.is_derby,
        importance=DERBY_IMPORTANCE if context.fixture.is_derby else NORMAL_IMPORTANCE,
    )
