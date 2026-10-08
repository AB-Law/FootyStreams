import pytest

from footystreams.sim.config import SimConfig
from footystreams.sim.decision import (
    choice_temperature,
    choose,
    decide,
    team_weights,
    urgency,
)
from footystreams.sim.options import ActionKind, Option, generate_options
from footystreams.sim.positioning import place_for_kickoff
from footystreams.sim.rng import SimRng
from footystreams.sim.state import MatchState
from footystreams.sim.threat import threat
from tests.factories.match import make_setup
from tests.factories.sim_play import make_state

CFG = SimConfig()


def _state() -> MatchState:
    state = make_state(make_setup())
    place_for_kickoff(state, "home")
    return state


def _put_carrier_at(state: MatchState, frame_x: float, frame_y: float = 0.5) -> None:
    state.carrier.x, state.carrier.y = frame_x, frame_y
    state.ball_x, state.ball_y = frame_x, frame_y


def test_threat__six_yard_box_is_about_a_tenth_and_own_box_almost_nothing() -> None:
    assert 0.08 < threat(0.95, 0.5) < 0.12
    assert threat(0.1, 0.5) < 0.001


def test_threat__central_beats_wide_and_is_monotone_in_x() -> None:
    assert threat(0.8, 0.5) > threat(0.8, 0.05)
    assert threat(0.8, 0.5) > threat(0.6, 0.5)


def test_urgency__trailing_late_is_positive_leading_late_is_negative_early_is_zero() -> None:
    state = _state()
    state.period, state.t_period, state.played_before_s = 2, 2000.0, 2700.0
    state.home.score, state.away.score = 0, 2
    assert urgency(state) > 0.5
    state.home.score, state.away.score = 2, 0
    assert urgency(state) < -0.5
    state.period, state.t_period = 1, 100.0
    assert urgency(state) == 0.0


def test_generate_options__always_contains_a_pass_and_a_dribble() -> None:
    state = _state()
    options = generate_options(state, 0.1, team_weights(state, CFG), CFG)
    kinds = {option.kind for option in options}
    assert {ActionKind.PASS, ActionKind.DRIBBLE} <= kinds


def test_generate_options__shot_only_when_in_range() -> None:
    state = _state()
    _put_carrier_at(state, 0.3)
    far = generate_options(state, 0.0, team_weights(state, CFG), CFG)
    assert ActionKind.SHOOT not in {option.kind for option in far}
    _put_carrier_at(state, 0.9)
    near = generate_options(state, 0.0, team_weights(state, CFG), CFG)
    assert ActionKind.SHOOT in {option.kind for option in near}


def test_generate_options__clearance_only_when_pressed_near_own_goal() -> None:
    state = _state()
    _put_carrier_at(state, 0.15)
    pressed = generate_options(state, 0.9, team_weights(state, CFG), CFG)
    relaxed = generate_options(state, 0.1, team_weights(state, CFG), CFG)
    assert ActionKind.CLEAR in {option.kind for option in pressed}
    assert ActionKind.CLEAR not in {option.kind for option in relaxed}


def test_generate_options__pass_options_are_never_to_the_carrier_himself() -> None:
    state = _state()
    options = generate_options(state, 0.1, team_weights(state, CFG), CFG)
    assert all(option.target is not state.carrier for option in options)


def _option(utility: float) -> Option:
    return Option(ActionKind.PASS, utility, 0.9, (0.5, 0.5), 0.0)


def test_choose__consumes_exactly_one_draw() -> None:
    rng = SimRng(3)
    choose([_option(1.0), _option(0.5), _option(0.2)], 60.0, rng, CFG)
    assert rng.draws == 1


def test_choose__good_decision_makers_pick_the_best_option_more_often() -> None:
    options = [_option(1.0), _option(0.7), _option(0.4)]

    def best_share(decisions: float) -> float:
        rng = SimRng(5)
        picks = [choose(options, decisions, rng, CFG) for _ in range(2000)]
        return sum(pick is options[0] for pick in picks) / len(picks)

    assert best_share(95.0) > best_share(20.0)


def test_choice_temperature__pressure_and_poor_decisions_raise_it() -> None:
    assert choice_temperature(50.0, 0.9, CFG) > choice_temperature(50.0, 0.0, CFG)
    assert choice_temperature(20.0, 0.0, CFG) > choice_temperature(90.0, 0.0, CFG)


def test_decide__is_deterministic_for_a_given_stream() -> None:
    first = decide(_state(), SimRng(11), CFG, 0.1)
    second = decide(_state(), SimRng(11), CFG, 0.1)
    assert (first.kind, first.end) == (second.kind, second.end)


@pytest.mark.parametrize("seed", range(5))
def test_decide__returns_a_valid_option_across_seeds(seed: int) -> None:
    option = decide(_state(), SimRng(seed), CFG, 0.1)
    assert 0.0 <= option.probability <= 1.0
    assert 0.0 <= option.end[0] <= 1.0
    assert 0.0 <= option.end[1] <= 1.0
