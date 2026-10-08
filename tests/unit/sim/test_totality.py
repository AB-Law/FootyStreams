"""Sim fuzz: generated valid setups must terminate and satisfy every match invariant."""

import pytest

from footystreams.domain.match import MatchSetup
from footystreams.events.open_play import GoalEvent, ShotEvent
from footystreams.sim import SimConfig, default_tables, run_match
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.sim import assert_match_valid

FORMATIONS = sorted(default_tables().formations)
MAX_PLAUSIBLE_GOALS = 14


def _setup(index: int) -> MatchSetup:
    home_formation = FORMATIONS[index % len(FORMATIONS)]
    away_formation = FORMATIONS[(index * 3 + 1) % len(FORMATIONS)]
    home_strength = 38 + (index * 7) % 52
    away_strength = 38 + (index * 11 + 5) % 52
    return make_demo_setup(
        home_strength=home_strength,
        away_strength=away_strength,
        home_formation=home_formation,
        away_formation=away_formation,
    )


def _check(index: int) -> None:
    setup = _setup(index)
    result = run_match(setup, 1000 + index, SimConfig(), default_tables())
    assert_match_valid(result.events, setup)
    goals = sum(isinstance(event, GoalEvent) for event in result.events)
    shots = sum(isinstance(event, ShotEvent) for event in result.events)
    assert shots >= 1
    assert goals <= MAX_PLAUSIBLE_GOALS


@pytest.mark.parametrize("index", range(8))
def test_run_match__generated_setups_terminate_and_pass_every_invariant(index: int) -> None:
    _check(index)


@pytest.mark.slow
@pytest.mark.parametrize("index", range(8, 208))
def test_run_match__two_hundred_generated_setups_are_total(index: int) -> None:
    _check(index)
