"""Builders for match stack models."""

from __future__ import annotations

from typing import Any

from footystreams.domain.club import ClubColours, Fanbase, KitSpec
from footystreams.domain.manager import Philosophy, SubHabits
from footystreams.domain.match import (
    ClubSnapshot,
    CornerTakers,
    LineupSlot,
    ManagerSnapshot,
    MatchSetup,
    PolicyRef,
    TeamSheet,
)
from footystreams.domain.mood import ResolvedMood
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import (
    ClubId,
    Duty,
    FixtureId,
    ManagerId,
    MatchId,
    PlayerId,
    Position,
    PreferredFoot,
    RefereeId,
    RoleId,
)
from footystreams.domain.weather import Weather, WeatherCondition
from tests.factories.player import (
    make_goalkeeping,
    make_hidden,
    make_mental,
    make_physical,
    make_player,
    make_technical,
)
from tests.factories.tactics import make_team_tactics


def make_player_snapshot(**overrides: Any) -> PlayerSnapshot:
    """Build a PlayerSnapshot from make_player defaults."""
    player = make_player()
    values: dict[str, Any] = {
        "id": PlayerId(str(player.id)),
        "known_as": player.known_as,
        "age": 26,
        "height_cm": player.height_cm,
        "weight_kg": player.weight_kg,
        "preferred_foot": PreferredFoot.RIGHT,
        "weak_foot": player.weak_foot,
        "technical": make_technical(),
        "mental": make_mental(),
        "physical": make_physical(),
        "goalkeeping": make_goalkeeping(),
        "hidden": make_hidden(),
        "position_competence": player.position_competence,
        "role_familiarity": player.role_familiarity,
        "traits": (),
        "form": 0.5,
        "morale": 0.5,
        "mood": ResolvedMood(),
        "fitness": 1.0,
        "fatigue": 0.0,
        "match_sharpness": 0.5,
        "volatility": 50,
        "sportsmanship": 50,
        "reputation": player.reputation,
        "squad_number": 9,
        "public_storylines": (),
    }
    values.update(overrides)
    return PlayerSnapshot(**values)


def make_team_sheet(*, club_id: str = "clb_home01", side: str = "home") -> TeamSheet:
    """Build a valid TeamSheet with eleven unique starters."""
    snapshots = {
        PlayerId(f"plr_{side}{index:04d}"): make_player_snapshot(
            id=PlayerId(f"plr_{side}{index:04d}"),
            known_as=f"{side}{index}",
            squad_number=index + 1,
            position_competence={Position.ST: 90, Position.GK: 10},
        )
        for index in range(14)
    }
    starter_ids = tuple(snapshots.keys())[:11]
    lineup = tuple(
        LineupSlot(
            slot=index, player_id=starter_ids[index], role=RoleId("poacher"), duty=Duty.ATTACK
        )
        for index in range(11)
    )
    bench = tuple(list(snapshots.keys())[11:14])
    colours = ClubColours(
        primary="#111111",
        secondary="#eeeeee",
        accent="#ff0000",
        home_kit=KitSpec(),
        away_kit=KitSpec(),
    )
    return TeamSheet(
        club=ClubSnapshot(
            id=ClubId(club_id),
            name=side.title(),
            short_code=side[:3].upper(),
            colours=colours,
            reputation=60,
        ),
        manager=ManagerSnapshot(
            id=ManagerId(f"mgr_{side}0001"),
            name=f"{side} manager",
            philosophy=Philosophy(
                possession_preference=0.5,
                directness=0.5,
                pressing_intensity=0.5,
                tempo=0.5,
                width=0.5,
                defensive_line=0.5,
                risk_taking=0.5,
            ),
            flexibility=0.5,
            sub_habits=SubHabits(
                earliest_minute=55,
                aggressiveness=0.5,
                fresh_legs_bias=0.5,
                protect_lead_bias=0.5,
                chase_game_bias=0.5,
                reacts_to_cards=0.5,
            ),
            tactical_knowledge=70,
        ),
        lineup=lineup,
        bench=bench,
        squad=snapshots,
        tactics=make_team_tactics(),
        policy=PolicyRef(policy_id="rules", policy_version="v1"),
        captain_id=starter_ids[0],
        penalty_takers=(starter_ids[0],),
        free_kick_takers=(starter_ids[0],),
        corner_takers=CornerTakers(left=starter_ids[0], right=starter_ids[1]),
        fanbase=Fanbase(
            size=20_000,
            passion=0.5,
            toxicity=0.3,
            fickleness=0.4,
            away_following=0.3,
        ),
    )


def make_setup(**overrides: Any) -> MatchSetup:
    """Build a MatchSetup both parallel tracks can share."""
    values: dict[str, Any] = {
        "match_id": MatchId("mch_test0001"),
        "fixture_id": FixtureId("fix_test0001"),
        "home": make_team_sheet(club_id="clb_home01", side="home"),
        "away": make_team_sheet(club_id="clb_away01", side="away"),
        "weather": Weather(
            condition=WeatherCondition.CLEAR,
            temperature_c=18.0,
            humidity=0.5,
            wind_speed_mps=2.0,
            wind_direction_deg=90,
            rain_mm_per_h=0.0,
            pitch_wetness=0.1,
            visibility=1.0,
        ),
        "referee_id": RefereeId("ref_test0001"),
        "attendance": 18_000,
        "is_derby": False,
        "importance": 0.5,
    }
    values.update(overrides)
    return MatchSetup(**values)
