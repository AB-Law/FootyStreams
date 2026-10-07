"""The pure match simulation: simulate_match(setup, seed, config, tables) -> events.

May import: domain, events. No I/O, no wall clock, no global randomness, no libm-dependent maths,
no numpy. Randomness only through the SimRng instance passed in.
Design: docs/design/02-simulation.md.
"""

from footystreams.sim.api import run_match, simulate_match
from footystreams.sim.config import SimConfig, config_hash, merge_config
from footystreams.sim.errors import InvalidSetupError
from footystreams.sim.tables import StaticTables, default_tables

__all__ = [
    "InvalidSetupError",
    "SimConfig",
    "StaticTables",
    "config_hash",
    "default_tables",
    "merge_config",
    "run_match",
    "simulate_match",
]
