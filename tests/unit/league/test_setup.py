from __future__ import annotations

import datetime as dt
from dataclasses import replace

import pytest

from footystreams.domain.injury import Injury, InjurySeverity, Suspension
from footystreams.domain.mood import ModifierSource, StateKind
from footystreams.domain.player import Player
from footystreams.domain.types import Position
from footystreams.domain.weather import WeatherCondition
from footystreams.league.lineup_ai import (
    BENCH_SIZE,
    SelectionTables,
    SquadTooSmallError,
    is_available,
    select_squad,
)
from footystreams.league.modifiers import ModifierSpec, new_modifier
from footystreams.league.setup import build_match_setup, build_team_sheet, match_id_for
from tests.factories.league_config import make_mood_config
from tests.factories.league_inputs import (
    make_match_context,
    make_setup_tables,
    make_team_inputs,
    make_world_setup,
)
from tests.factories.world import make_world

WORLD = make_world(1)
TABLES = make_setup_tables()


def _select(squad: list[Player], today: dt.date | None = None):  # type: ignore[no-untyped-def]
    club = WORLD.clubs[0]
    tactics = club.default_tactics
    context = make_match_context(WORLD)
    return select_squad(
        squad,
        TABLES.formations.formations[tactics.formation],
        tactics,
        (today or context.today, SelectionTables(TABLES.roles, TABLES.recovery)),
    )


def _squad() -> list[Player]:
    return list(make_team_inputs(WORLD, 0).squad)


def _hurt(player: Player, today: dt.date) -> Player:
    injury = Injury(
        type="x",
        body_part="knee",
        severity=InjurySeverity.MODERATE,
        started_on=today,
        expected_return_on=today + dt.timedelta(days=20),
    )
    return player.model_copy(update={"current_injury": injury})


def test_select_squad__full_squad__fills_eleven_distinct_slots_and_a_bench_with_a_keeper() -> None:
    selection = _select(_squad())
    ids = [slot.player_id for slot in selection.lineup]
    assert len(set(ids)) == 11
    assert [slot.slot for slot in selection.lineup] == list(range(11))
    assert len(selection.bench) <= BENCH_SIZE
    assert not set(ids) & set(selection.bench)
    by_id = {p.id: p for p in _squad()}
    assert by_id[ids[0]].primary_position is Position.GK
    assert any(by_id[b].primary_position is Position.GK for b in selection.bench)


def test_select_squad__injured_and_suspended__are_left_out() -> None:
    squad = _squad()
    today = make_match_context(WORLD).today
    first_xi = [slot.player_id for slot in _select(squad).lineup]
    hurt = _hurt(next(p for p in squad if p.id == first_xi[3]), today)
    banned = next(p for p in squad if p.id == first_xi[5]).model_copy(
        update={"suspension": Suspension(matches_remaining=1, reason="red card")}
    )
    squad = [hurt if p.id == hurt.id else banned if p.id == banned.id else p for p in squad]
    picked = {slot.player_id for slot in _select(squad).lineup}
    assert hurt.id not in picked
    assert banned.id not in picked
    assert not is_available(hurt, today)
    assert not is_available(banned, today)


def test_select_squad__tired_starter__is_rotated_out_for_an_equal_who_is_rested() -> None:
    squad = _squad()
    starter_id = _select(squad).lineup[8].player_id
    tired = next(p for p in squad if p.id == starter_id).model_copy(update={"fatigue": 1.0})
    twin = tired.model_copy(update={"id": "plr_twin1", "fatigue": 0.0})
    picked = {
        slot.player_id
        for slot in _select([tired, twin, *(p for p in squad if p.id != tired.id)]).lineup
    }
    assert twin.id in picked
    assert tired.id not in picked


def test_select_squad__too_few_fit__uses_the_injured_rather_than_failing() -> None:
    today = make_match_context(WORLD).today
    squad = [_hurt(p, today) for p in _squad()]
    assert len(_select(squad).lineup) == 11


def test_select_squad__fewer_than_eleven_players__raises() -> None:
    with pytest.raises(SquadTooSmallError):
        _select(_squad()[:10])


def test_select_squad__set_pieces__come_from_the_starters() -> None:
    selection = _select(_squad())
    starters = {slot.player_id for slot in selection.lineup}
    assert selection.captain in starters
    assert set(selection.penalty_takers) <= starters
    assert {selection.corner_takers.left, selection.corner_takers.right} <= starters


def test_build_match_setup__real_world__is_a_valid_setup_for_the_fixture() -> None:
    setup = make_world_setup()
    context = make_match_context(WORLD)
    assert setup.match_id == match_id_for(context.fixture)
    assert setup.home.club.id == WORLD.clubs[0].id
    assert setup.away.club.id == WORLD.clubs[1].id
    assert len(setup.home.lineup) == len(setup.away.lineup) == 11


def test_build_team_sheet__private_modifier__shapes_mood_but_shows_no_storyline() -> None:
    starter = make_world_setup().home.lineup[9].player_id
    today = make_match_context(WORLD).today
    spec = ModifierSpec(StateKind.PERSONAL_TURMOIL, starter, 1.0, ModifierSource(origin="x"))
    private = new_modifier(spec, today, make_mood_config())
    inputs = make_team_inputs(WORLD, 0, {starter: [private]})
    sheet = build_team_sheet(inputs, WORLD.clubs[1].id, make_match_context(WORLD), TABLES)
    snapshot = sheet.squad[starter]
    assert snapshot.mood.mental_mult < 1.0
    assert snapshot.public_storylines == ()
    assert private.id in snapshot.mood.contributing_modifier_ids


def test_build_match_setup__mood_modifier_on_a_starter__lowers_his_snapshot_multipliers() -> None:
    inputs = make_team_inputs(WORLD, 0)
    base = build_match_setup(
        (inputs, make_team_inputs(WORLD, 1)), make_match_context(WORLD), TABLES
    )
    starter = base.home.lineup[9].player_id
    mood = make_mood_config()
    today = make_match_context(WORLD).today
    spec = ModifierSpec(StateKind.MEDIA_STORM, starter, 1.0, ModifierSource(origin="x"))
    moody = replace(inputs, modifiers={starter: [new_modifier(spec, today, mood)]})
    setup = build_match_setup(
        (moody, make_team_inputs(WORLD, 1)), make_match_context(WORLD), TABLES
    )
    assert setup.home.squad[starter].mood.mental_mult < base.home.squad[starter].mood.mental_mult
    assert setup.home.squad[starter].public_storylines == ("media_storm",)


def test_build_match_setup__context_weather__is_carried_through() -> None:
    context = make_match_context(WORLD)
    rainy = replace(
        context, weather=context.weather.model_copy(update={"condition": WeatherCondition.SNOW})
    )
    sides = (make_team_inputs(WORLD, 0), make_team_inputs(WORLD, 1))
    assert build_match_setup(sides, rainy, TABLES).weather.condition is WeatherCondition.SNOW
