import pytest

from footystreams.sim import SimConfig, merge_config
from footystreams.sim.config import HomeAdvantageConfig
from footystreams.sim.effective import Skills
from footystreams.sim.homeadv import NO_CROWD, Crowd, apply_crowd, crowd_level, crowd_of
from tests.factories.match import make_setup
from tests.factories.sim_play import make_state

CFG = HomeAdvantageConfig(enabled=True)


def _skills() -> Skills:
    return make_state(make_setup()).home.players[5].skills


def test_crowd_level__empty_ground_has_none_and_full_loud_ground_more() -> None:
    empty = make_setup(attendance=0)
    full = make_setup(attendance=40_000)
    assert crowd_level(empty, CFG) == 0.0
    assert crowd_level(full, CFG) > crowd_level(make_setup(attendance=10_000), CFG) > 0.0
    assert crowd_level(full, CFG) <= 1.0


def test_crowd_of__off_is_no_crowd_and_on_carries_the_fans_toxicity() -> None:
    setup = make_setup()
    assert crowd_of(setup, HomeAdvantageConfig()) is NO_CROWD
    crowd = crowd_of(setup, CFG)
    assert crowd.level > 0.0
    assert crowd.toxicity == setup.home.fanbase.toxicity  # type: ignore[union-attr]


def test_apply_crowd__home_gains_mental_attributes_proportionally_to_the_crowd() -> None:
    skills = _skills()
    small = apply_crowd(skills, "home", Crowd(0.2, 0.3), CFG, 1.0)
    large = apply_crowd(skills, "home", Crowd(1.0, 0.3), CFG, 1.0)
    assert skills.composure < small.composure < large.composure <= skills.composure * 1.03
    assert large.finishing == skills.finishing


def test_apply_crowd__away_loses_a_little_composure_more_when_the_crowd_is_toxic() -> None:
    skills = _skills()
    mild = apply_crowd(skills, "away", Crowd(1.0, 0.0), CFG, 1.0)
    toxic = apply_crowd(skills, "away", Crowd(1.0, 1.0), CFG, 1.0)
    assert toxic.composure < mild.composure < skills.composure
    assert toxic.composure > skills.composure * 0.97
    assert toxic.vision == skills.vision


def test_apply_crowd__scale_zero_or_no_crowd_changes_nothing() -> None:
    skills = _skills()
    assert apply_crowd(skills, "home", Crowd(1.0, 1.0), CFG, 0.0) is skills
    assert apply_crowd(skills, "away", NO_CROWD, CFG, 1.0) is skills


def test_build_state__with_home_advantage_on_the_home_team_is_a_touch_better_than_away() -> None:
    on = merge_config(SimConfig(), {"home_advantage": {"enabled": True}})
    state = make_state(make_setup(), config=on)
    off = make_state(make_setup(), config=SimConfig())
    assert state.home.players[5].skills.composure > off.home.players[5].skills.composure
    assert state.away.players[5].skills.composure < off.away.players[5].skills.composure
    assert pytest.approx(state.home.players[5].skills.pace) == off.home.players[5].skills.pace
