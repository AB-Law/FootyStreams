from __future__ import annotations

import pytest

from footystreams.balance.runner import BalanceRunner, _slices, play_only
from footystreams.balance.sample import sample_from
from footystreams.sim import SimConfig, run_match
from tests.factories.balance_runs import make_balance_scenarios, make_balance_tables

pytestmark = pytest.mark.timeout(240)


def test_slices__cover_the_range_exactly_once_in_order() -> None:
    assert _slices(10, 4) == [(0, 3), (3, 6), (6, 9), (9, 10)]
    assert _slices(3, 8) == [(0, 1), (1, 2), (2, 3)]


def test_samples__are_taken_from_the_matches_that_were_played() -> None:
    scenarios = make_balance_scenarios()[:2]
    with BalanceRunner(scenarios, make_balance_tables(), 1) as runner:
        samples = runner.run(SimConfig())

    assert [s.gap for s in samples] == [sc.gap for sc in scenarios]
    assert all(
        s.home.possession + s.away.possession == pytest.approx(1.0, abs=0.01) for s in samples
    )
    assert all(s.goals_second_half <= s.goals for s in samples)


@pytest.mark.slow
def test_run__more_workers_give_exactly_the_same_samples() -> None:
    scenarios = make_balance_scenarios()[:6]
    tables = make_balance_tables()
    with BalanceRunner(scenarios, tables, 1) as serial:
        expected = serial.run(SimConfig())
    with BalanceRunner(scenarios, tables, 2) as parallel:
        actual = parallel.run(SimConfig())

    assert actual == expected


def test_run__a_changed_knob_changes_the_samples_and_the_same_config_repeats() -> None:
    scenarios = make_balance_scenarios()[:4]
    with BalanceRunner(scenarios, make_balance_tables(), 1) as runner:
        base = runner.run(SimConfig())
        again = runner.run(SimConfig())
        neutral_venue = runner.run(SimConfig(home_advantage_scale=0.0))

    assert base == again
    assert neutral_venue != base


def test_play_only__samples_are_identical_with_and_without_the_causal_context() -> None:
    scenarios = make_balance_scenarios()[:6]
    tables = make_balance_tables()
    with_context = [
        sample_from(run_match(s.setup, s.seed, SimConfig(), tables), s.gap) for s in scenarios
    ]
    with BalanceRunner(scenarios, tables, 1) as runner:
        lean = runner.run(SimConfig())

    assert lean == with_context
    assert play_only(SimConfig()).context.enabled is False
