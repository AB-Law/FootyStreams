import pytest

from footystreams.sim import SimConfig, default_tables, run_match
from footystreams.sim.config import RefereeConfig
from footystreams.sim.referee import (
    NEUTRAL_REFEREE,
    RefereeProfile,
    call_probability,
    call_threshold,
    crowd_pressure,
    home_tilt,
    is_called,
    referee_profile,
)
from footystreams.sim.rng import SimRng
from tests.factories.referee import make_referee
from tests.factories.sim_play import make_play
from tests.factories.sim_teams import DEMO_REFEREE_ID, make_demo_setup

CFG = RefereeConfig()


def _profile(**overrides: float) -> RefereeProfile:
    values = {
        "strictness": 0.5,
        "consistency": 0.5,
        "home_bias": 0.0,
        "card_tendency": 0.5,
        "advantage_tendency": 0.5,
        "added_time_generosity": 0.5,
        "penalty_propensity": 0.5,
    }
    values.update(overrides)
    return RefereeProfile(**values)


def test_referee_profile__without_a_referee_is_neutral() -> None:
    assert referee_profile(None) is NEUTRAL_REFEREE


def test_referee_profile__copies_the_model_sliders() -> None:
    profile = referee_profile(make_referee(strictness=0.9, home_bias=0.3, card_tendency=0.2))
    assert (profile.strictness, profile.home_bias, profile.card_tendency) == (0.9, 0.3, 0.2)


def test_crowd_pressure__scales_with_attendance_and_is_capped() -> None:
    assert crowd_pressure(0, CFG) == 0.0
    assert crowd_pressure(CFG.crowd_capacity * 3, CFG) == 1.0
    assert 0.0 < crowd_pressure(10_000, CFG) < 1.0


def test_call_threshold__strict_referees_have_lower_thresholds() -> None:
    strict = call_threshold(_profile(strictness=1.0), 0.0, 0.0, CFG)
    lenient = call_threshold(_profile(strictness=0.0), 0.0, 0.0, CFG)
    assert strict < lenient


def test_call_threshold__inconsistency_amplifies_noise_and_consistency_removes_it() -> None:
    steady = call_threshold(_profile(consistency=1.0), 0.0, 2.0, CFG)
    erratic = call_threshold(_profile(consistency=0.0), 0.0, 2.0, CFG)
    assert steady == call_threshold(_profile(consistency=1.0), 0.0, 0.0, CFG)
    assert erratic != steady


def test_call_probability__rises_with_severity_and_is_half_at_the_threshold() -> None:
    assert call_probability(0.5, 0.5, CFG) == 0.5
    assert call_probability(0.9, 0.5, CFG) > call_probability(0.3, 0.5, CFG)


def test_home_tilt__a_home_biased_referee_is_harder_on_the_away_side() -> None:
    biased = _profile(home_bias=0.4)
    away = home_tilt(biased, "away", 1.0, CFG)
    home = home_tilt(biased, "home", 1.0, CFG)
    assert away > 0.0 > home
    assert call_threshold(biased, away, 0.0, CFG) < call_threshold(biased, home, 0.0, CFG)


def test_home_tilt__an_empty_ground_removes_the_bias() -> None:
    assert home_tilt(_profile(home_bias=0.4), "away", 0.0, CFG) == 0.0


def test_is_called__strict_referee_calls_more_contacts_than_a_lenient_one() -> None:
    def calls(profile: RefereeProfile) -> int:
        rng = SimRng(4)
        return sum(is_called(profile, 0.45, 0.0, CFG, rng) for _ in range(2000))

    assert calls(_profile(strictness=1.0)) > calls(_profile(strictness=0.0))


def test_is_called__consumes_a_noise_draw_and_a_decision_draw() -> None:
    rng = SimRng(1)
    is_called(NEUTRAL_REFEREE, 0.5, 0.0, CFG, rng)
    assert rng.draws == 5  # gauss = 4 uniforms, plus the decision


def test_run_match__accepts_a_referee_and_stays_deterministic() -> None:
    setup, referee = make_demo_setup(), make_referee(id=DEMO_REFEREE_ID, strictness=0.8)
    first = run_match(setup, 3, SimConfig(), default_tables(), referee)
    second = run_match(setup, 3, SimConfig(), default_tables(), referee)
    assert first.log_digest == second.log_digest


def test_play__carries_the_discipline_and_setpiece_streams_and_the_referee() -> None:
    play = make_play(referee=make_referee(strictness=0.9))
    assert play.referee.strictness == pytest.approx(0.9)
    assert play.discipline is not play.setpiece
    assert play.discipline is not play.rng
