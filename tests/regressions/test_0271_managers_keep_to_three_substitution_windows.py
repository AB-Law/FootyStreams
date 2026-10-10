"""A side must never use more substitution windows than the rules allow (invariant M08).

The M8 calibration raised the simulator's `manager.max_windows` from three to five because the AI
made one change per stoppage and three windows capped a side at 3.0 changes against 4.2 in a league.
The rule is five changes in three windows plus half-time, and M08 enforces it, so 11 of the 12
matches of a generated league broke it. The pre-air gate in the runtime quarantined nearly every
match, so the engine broadcast nothing (`tests/unit/cli/test_engine_cli.py`, slow tier).
"""

from __future__ import annotations

import pytest

from footystreams.domain.competition import MatchRules
from footystreams.sim import SimConfig, run_match
from footystreams.sim.config_manager import ManagerConfig
from tests.factories.balance_runs import make_balance_scenarios, make_balance_tables
from tests.helpers.sim import assert_match_valid

# Scenarios of the generated league that used four or five windows before the fix.
OVERUSED_WINDOWS = (0, 4, 9)


def test_manager_config__the_limits_are_the_competition_rules() -> None:
    rules, manager = MatchRules(), ManagerConfig()

    assert manager.max_windows == rules.sub_windows
    assert manager.max_subs == rules.subs_max


@pytest.mark.parametrize("index", OVERUSED_WINDOWS)
def test_run_match__a_league_match_keeps_to_the_substitution_rules(index: int) -> None:
    scenario = make_balance_scenarios(12, 1)[index]

    result = run_match(scenario.setup, scenario.seed, SimConfig(), make_balance_tables())

    assert_match_valid(result.events, scenario.setup)
