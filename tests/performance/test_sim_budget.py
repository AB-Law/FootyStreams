"""Performance tripwire for the simulator (benchmark id M4-match-budget).

The design budget is a mean of 150 ms a match (docs/design/11 section 6.1); the milestone tripwire
only catches order-of-magnitude regressions and uses the best of a few CPU-time measurements so
a busy machine does not make it flaky. The real budget is asserted by the M8 profiling pass.
"""

import sys
import time

import pytest

from footystreams.sim import SimConfig, default_tables, run_match
from tests.factories.sim_teams import make_demo_setup

# Raised from 0.5 s by the living-movement work (SIM 0.6.0): a match went from 0.23 s to about
# 0.33 s of CPU alone (0.53 s under the gate's parallel load) for pressing, marking, spacing and
# set-piece shapes. Still an order-of-magnitude tripwire: the 150 ms budget stays for the M8
# optimisation pass.
TRIPWIRE_S = 0.75
RUNS = 3


def test_run_match__best_cpu_time_of_a_few_runs_stays_under_the_tripwire() -> None:
    if sys.gettrace() is not None:
        pytest.skip("timing is meaningless under a tracer (coverage slows the sim about 4x)")
    setup, tables, config = make_demo_setup(), default_tables(), SimConfig()
    run_match(setup, 0, config, tables)  # warm-up: imports, caches
    best = float("inf")
    for seed in range(RUNS):
        started = time.process_time()
        run_match(setup, seed, config, tables)
        best = min(best, time.process_time() - started)
    assert best < TRIPWIRE_S
