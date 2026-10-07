from dataclasses import replace

import pytest

from footystreams.sim.actions.dribbling import dribble_success_probability
from footystreams.sim.actions.passing import (
    PassAttempt,
    PassKind,
    classify_pass,
    pass_skill,
    pass_success_probability,
)
from footystreams.sim.actions.shooting import geometry_xg, shot_chance
from footystreams.sim.config import DribbleConfig, PassConfig, PressureConfig, ShotConfig
from footystreams.sim.geometry import PITCH_LENGTH_M
from footystreams.sim.pressure import nearest_opponents, openness, pressure_on
from footystreams.sim.state import MatchState
from tests.factories.match import make_setup
from tests.factories.sim_play import make_state

PRESSURE = PressureConfig()
PASSING = PassConfig()
SHOT = ShotConfig()


def _state() -> MatchState:
    return make_state(make_setup())


def _isolate(state: MatchState) -> None:
    """Move every away player to the far corner so tests place defenders explicitly."""
    for player in state.away.players:
        player.x, player.y = 0.99, 0.99


def test_nearest_opponents__sorted_by_distance_and_limited_to_count() -> None:
    state = _state()
    nearest = nearest_opponents(state.away, 0.5, 0.5, 3)
    gaps = [gap for gap, _ in nearest]
    assert len(nearest) == 3
    assert gaps == sorted(gaps)


def test_pressure_on__no_defender_near__is_zero() -> None:
    state = _state()
    _isolate(state)
    carrier = state.home.players[8]
    carrier.x, carrier.y = 0.2, 0.2
    assert pressure_on(carrier, state.away, PRESSURE) == 0.0


def test_pressure_on__defender_on_top_of_carrier__is_high_and_bounded() -> None:
    state = _state()
    _isolate(state)
    carrier = state.home.players[8]
    carrier.x, carrier.y = 0.5, 0.5
    for defender in state.away.players[:3]:
        defender.x, defender.y = 0.5 + 0.5 / PITCH_LENGTH_M, 0.5
    assert 0.4 < pressure_on(carrier, state.away, PRESSURE) <= 1.0


def test_openness__receiver_in_space_beats_marked_receiver() -> None:
    state = _state()
    _isolate(state)
    carrier = state.home.players[8]
    carrier.x, carrier.y = 0.3, 0.5
    marker = state.away.players[0]
    marker.x, marker.y = 0.60, 0.5
    free = openness(carrier, 0.5, 0.1, state.away, PRESSURE)
    marked = openness(carrier, 0.6, 0.5, state.away, PRESSURE)
    assert free > marked


@pytest.mark.parametrize(
    ("carrier", "mate", "length", "expected"),
    [
        ((0.5, 0.5), (0.4, 0.5), 10.0, PassKind.BACK),
        ((0.5, 0.5), (0.58, 0.5), 9.0, PassKind.SHORT),
        ((0.2, 0.5), (0.7, 0.4), 50.0, PassKind.LONG),
        ((0.4, 0.5), (0.62, 0.45), 24.0, PassKind.THROUGH),
        ((0.8, 0.05), (0.92, 0.5), 25.0, PassKind.CROSS),
    ],
)
def test_classify_pass__by_geometry(
    carrier: tuple[float, float], mate: tuple[float, float], length: float, expected: PassKind
) -> None:
    assert classify_pass(carrier, mate, length, PASSING) is expected


def _attempt(
    kind: PassKind = PassKind.SHORT, length_m: float = 15.0, **overrides: float
) -> PassAttempt:
    values = {
        "skill": 60.0,
        "receiver_touch": 55.0,
        "pressure": 0.1,
        "openness": 0.8,
    }
    values.update(overrides)
    return PassAttempt(kind=kind, length_m=length_m, **values)


def test_pass_success__better_skill_and_less_pressure_help() -> None:
    base = pass_success_probability(_attempt(), PASSING)
    assert pass_success_probability(_attempt(skill=90.0), PASSING) > base
    assert pass_success_probability(_attempt(pressure=0.9), PASSING) < base
    assert pass_success_probability(_attempt(openness=0.1), PASSING) < base


def test_pass_success__longer_and_harder_kinds_are_less_likely() -> None:
    short = pass_success_probability(_attempt(), PASSING)
    long = pass_success_probability(_attempt(kind=PassKind.LONG, length_m=40.0), PASSING)
    cross = pass_success_probability(_attempt(kind=PassKind.CROSS, length_m=25.0), PASSING)
    assert long < short
    assert cross < short


def test_pass_success__is_clamped_to_configured_bounds() -> None:
    hopeless = pass_success_probability(_attempt(pressure=1.0, openness=0.0, skill=1.0), PASSING)
    assert PASSING.min_probability <= hopeless <= PASSING.max_probability


def test_pass_skill__uses_the_attribute_for_the_kind() -> None:
    skills = _state().home.players[5].skills
    boosted = replace(skills, long_passing=99.0)
    assert pass_skill(PassKind.LONG, boosted) == 99.0
    assert pass_skill(PassKind.SHORT, boosted) == skills.short_passing


@pytest.mark.parametrize(
    ("metres_out", "low", "high"),
    [(6.0, 0.26, 0.38), (11.0, 0.12, 0.20), (18.0, 0.04, 0.08), (30.0, 0.005, 0.02)],
)
def test_geometry_xg__matches_the_documented_anchors(
    metres_out: float, low: float, high: float
) -> None:
    assert low <= geometry_xg(1.0 - metres_out / PITCH_LENGTH_M, 0.5, SHOT) <= high


def test_geometry_xg__tight_angle_is_worth_less_than_central() -> None:
    assert geometry_xg(0.9, 0.05, SHOT) < geometry_xg(0.9, 0.5, SHOT)


def test_shot_chance__pressure_lowers_and_finishing_raises_xg() -> None:
    skills = _state().home.players[10].skills
    calm = shot_chance((0.9, 0.5), skills, 0.0, SHOT).xg
    harried = shot_chance((0.9, 0.5), skills, 1.0, SHOT).xg
    clinical = shot_chance((0.9, 0.5), replace(skills, finishing=95.0), 0.0, SHOT).xg
    assert harried < calm < clinical


def test_shot_chance__uses_long_shots_from_range() -> None:
    skills = replace(_state().home.players[10].skills, finishing=1.0, long_shots=99.0)
    from_range = shot_chance((0.7, 0.5), skills, 0.0, SHOT)
    assert from_range.xg > 0.9 * from_range.geometry_xg


def test_dribble_success__unmarked_is_max_and_better_dribbler_wins_more() -> None:
    cfg = DribbleConfig()
    skills = _state().home.players[8].skills
    defender = _state().away.players[2].skills
    assert dribble_success_probability(skills, None, 0.0, cfg) == cfg.max_probability
    weak = dribble_success_probability(replace(skills, dribbling=10.0), defender, 0.3, cfg)
    strong = dribble_success_probability(replace(skills, dribbling=95.0), defender, 0.3, cfg)
    assert strong > weak


def test_match_state_helpers__attackers_and_defenders_follow_the_carrier() -> None:
    state = _state()
    assert state.attackers is state.home
    assert state.defenders is state.away
