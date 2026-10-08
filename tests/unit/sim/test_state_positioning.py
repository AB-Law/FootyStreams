from dataclasses import replace

import pytest

from footystreams.domain.types import FormationId, Position
from footystreams.sim.config import PositionConfig
from footystreams.sim.errors import InvalidSetupError
from footystreams.sim.geometry import distance_m
from footystreams.sim.positioning import (
    KICKOFF_MAX_X,
    move_toward,
    place_for_kickoff,
    speed_mps,
    target_in_frame,
    update_positions,
)
from footystreams.sim.rng import SimRng
from footystreams.sim.state import Line, MatchState, build_state, line_of
from footystreams.sim.tables import default_tables
from tests.factories.match import make_setup, make_team_sheet

CFG = PositionConfig()


def _state() -> MatchState:
    return build_state(make_setup(), default_tables(), SimRng(1))


def test_build_state__eleven_players_per_side_in_slot_order_on_their_slots() -> None:
    state = _state()
    assert [p.slot for p in state.home.players] == list(range(11))
    assert len(state.away.players) == 11
    assert state.home.players[0].position is Position.GK


def test_build_state__away_team_attacks_the_other_way_and_starts_mirrored() -> None:
    state = _state()
    striker_home = state.home.players[10]
    striker_away = state.away.players[10]
    assert state.home.attack_dir == 1
    assert state.away.attack_dir == -1
    assert striker_home.x > 0.5 > striker_away.x


def test_build_state__unknown_formation__raises_invalid_setup_with_the_club_id() -> None:
    sheet = make_team_sheet()
    bad = sheet.model_copy(
        update={"tactics": sheet.tactics.model_copy(update={"formation": FormationId("999")})}
    )
    with pytest.raises(InvalidSetupError, match="clb_home01"):
        build_state(make_setup(home=bad), default_tables(), SimRng(1))


def test_build_state__draws_one_day_form_per_player_from_the_given_stream() -> None:
    rng = SimRng(1)
    build_state(make_setup(), default_tables(), rng)
    assert rng.draws == 22 * 4


def test_line_of__covers_every_position() -> None:
    assert {line_of(position) for position in Position} == set(Line)


def test_move_toward__never_overshoots_and_respects_the_step() -> None:
    state = _state()
    player = state.home.players[5]
    start_x, start_y = player.x, player.y
    move_toward(player, 0.9, 0.9, 5.0)
    assert distance_m(start_x, start_y, player.x, player.y) == pytest.approx(5.0)
    move_toward(player, 0.9, 0.9, 1000.0)
    assert (player.x, player.y) == (0.9, 0.9)


def test_speed_mps__faster_players_are_faster() -> None:
    state = _state()
    player = state.home.players[3]
    fast_skills = replace(player.skills, pace=100.0)
    slow_skills = replace(player.skills, pace=1.0)
    player.skills = fast_skills
    fast = speed_mps(player, CFG)
    player.skills = slow_skills
    assert fast > speed_mps(player, CFG)


def test_target_in_frame__team_in_possession_sits_higher_than_out_of_possession() -> None:
    state = _state()
    team = state.home
    defender = team.players[2]
    ball = (0.5, 0.5)
    higher = target_in_frame(team, defender, ball, True, CFG)[0]
    lower = target_in_frame(team, defender, ball, False, CFG)[0]
    assert higher > lower


def test_target_in_frame__players_are_pulled_toward_the_ball_side() -> None:
    state = _state()
    midfielder = state.home.players[6]
    left = target_in_frame(state.home, midfielder, (0.5, 0.1), False, CFG)[1]
    right = target_in_frame(state.home, midfielder, (0.5, 0.9), False, CFG)[1]
    assert left < right


def test_update_positions__moves_players_toward_targets_but_not_the_carrier() -> None:
    state = _state()
    place_for_kickoff(state, "home")
    carrier = state.carrier
    carrier_xy = (carrier.x, carrier.y)
    other = state.home.players[8]
    before = (other.x, other.y)
    state.ball_x, state.ball_y = 0.8, 0.2
    update_positions(state, 4.0, CFG)
    assert (carrier.x, carrier.y) == carrier_xy
    assert (other.x, other.y) != before


def test_place_for_kickoff__everyone_in_own_half_but_the_kicker_on_the_centre_spot() -> None:
    state = _state()
    place_for_kickoff(state, "away")
    assert state.carrier.side == "away"
    assert (state.ball_x, state.ball_y) == (0.5, 0.5)
    for player in state.home.players:
        assert player.x <= KICKOFF_MAX_X
    for player in state.away.players:
        assert player is state.carrier or player.x >= 1.0 - KICKOFF_MAX_X
