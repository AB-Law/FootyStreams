from dataclasses import replace

import pytest

from footystreams.domain.types import PlayerId
from footystreams.sim import SimConfig, default_tables, merge_config
from footystreams.sim.config import FatigueConfig
from footystreams.sim.engine import MatchEngine
from footystreams.sim.fatigue import (
    advance_exhaustion,
    away_travel,
    energy_multipliers,
    halftime_recovery,
    initial_exhaustion,
    player_drain,
    role_load,
    team_factor,
)
from footystreams.sim.state import Line, MatchState
from footystreams.sim.weather import NEUTRAL, Conditions
from tests.factories.match import make_player_snapshot, make_setup
from tests.factories.sim_play import make_state
from tests.factories.sim_teams import make_demo_setup

CFG = FatigueConfig(enabled=True)
ON = merge_config(SimConfig(), {"fatigue": {"enabled": True}})


def _state(config: SimConfig = ON) -> MatchState:
    return make_state(make_setup(), config=config)


def test_initial_exhaustion__combines_carried_fatigue_and_lack_of_fitness() -> None:
    fresh = make_player_snapshot(fatigue=0.0, fitness=1.0)
    tired = make_player_snapshot(fatigue=0.8, fitness=0.6)
    assert initial_exhaustion(fresh, CFG) == 0.0
    assert initial_exhaustion(tired, CFG) == pytest.approx(0.6 * 0.8 + 0.4 * 0.4)


def test_energy_multipliers__physical_goes_first_and_all_fall_with_exhaustion() -> None:
    early = energy_multipliers(0.3, CFG)
    late = energy_multipliers(0.9, CFG)
    assert early.physical < 1.0
    assert early.mental == 1.0
    assert late.physical < early.physical
    assert late.technical < early.technical < 1.0 + 1e-9
    assert late.mental < early.mental


def test_energy_multipliers__fresh_players_are_unaffected() -> None:
    fresh = energy_multipliers(0.0, CFG)
    assert (fresh.technical, fresh.mental, fresh.physical) == (1.0, 1.0, 1.0)


def test_role_load__keepers_tire_least() -> None:
    assert (
        role_load(Line.KEEPER, CFG) < role_load(Line.DEFENCE, CFG) < role_load(Line.MIDFIELD, CFG)
    )


def test_player_drain__poor_stamina_heat_and_rain_all_raise_it() -> None:
    player = _state().home.players[5]
    base = player_drain(player, NEUTRAL, 0.0, CFG)
    tired = replace(player, skills=replace(player.skills, stamina=10.0))
    assert player_drain(tired, NEUTRAL, 0.0, CFG) > base
    hot = Conditions(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0)
    wet = Conditions(0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0)
    assert player_drain(player, hot, 0.0, CFG) > base
    assert player_drain(player, wet, 0.0, CFG) > base
    assert player_drain(player, NEUTRAL, 0.1, CFG) > base


def test_player_drain__a_keeper_drains_a_quarter_as_fast_as_a_midfielder() -> None:
    state = _state()
    keeper, midfielder = state.home.players[0], state.home.players[5]
    assert player_drain(keeper, NEUTRAL, 0.0, CFG) < 0.5 * player_drain(
        midfielder, NEUTRAL, 0.0, CFG
    )


def test_away_travel__home_players_have_none_and_away_players_a_small_extra() -> None:
    sheet = make_setup().home
    assert away_travel(None, CFG) == 0.0
    assert 0.0 < away_travel(sheet, CFG) < 0.1


def test_team_factor__playing_a_man_down_and_hard_pressing_raise_it() -> None:
    team = _state().home
    base = team_factor(team, CFG)
    team.players.pop()
    assert team_factor(team, CFG) > base


def test_advance_exhaustion__only_ever_increases_it_and_weakens_pace() -> None:
    state = _state()
    player = state.home.players[5]
    before_exhaustion, before_pace = player.exhaustion, player.skills.pace
    for _ in range(200):
        previous = player.exhaustion
        advance_exhaustion(state, 27.0, CFG)
        assert player.exhaustion >= previous
    assert player.exhaustion > before_exhaustion
    assert player.skills.pace < before_pace


def test_advance_exhaustion__is_capped() -> None:
    state = _state()
    advance_exhaustion(state, 10_000_000.0, CFG)
    assert max(p.exhaustion for p in state.home.players) == CFG.max_exhaustion


def test_halftime_recovery__lowers_exhaustion_and_never_below_zero() -> None:
    state = _state()
    advance_exhaustion(state, 2700.0, CFG)
    player = state.home.players[5]
    tired = player.exhaustion
    halftime_recovery(state, CFG)
    assert player.exhaustion == pytest.approx(tired - CFG.halftime_recovery)
    for _ in range(50):
        halftime_recovery(state, CFG)
    assert player.exhaustion == 0.0


def test_build_state__with_fatigue_off_nobody_is_tired_and_skills_are_the_base() -> None:
    state = _state(SimConfig())
    player = state.home.players[5]
    assert player.exhaustion == 0.0
    assert player.base_skills is player.skills


def test_match__exhaustion_never_decreases_within_a_half_and_only_halftime_lowers_it() -> None:
    engine = MatchEngine(make_demo_setup(), 5, ON, default_tables())
    state = engine.state
    previous: dict[PlayerId, float] = {}
    last_period = 1
    for _ in engine.run():
        current = {
            p.player_id: p.exhaustion for team in (state.home, state.away) for p in team.players
        }
        if state.period == last_period:
            assert all(current[pid] >= previous.get(pid, 0.0) - 1e-12 for pid in current)
        last_period = state.period
        previous = current
    assert max(previous.values()) > 0.3
