"""Builders for simulation internals: a ready-to-use Play at kick-off."""

from __future__ import annotations

from footystreams.domain.match import MatchSetup
from footystreams.sim.config import SimConfig
from footystreams.sim.emit import EventEmitter
from footystreams.sim.play import Play
from footystreams.sim.positioning import place_for_kickoff
from footystreams.sim.rng import SimRng
from footystreams.sim.state import build_state
from footystreams.sim.tables import default_tables
from tests.factories.match import make_setup


def make_play(
    seed: int = 1, setup: MatchSetup | None = None, config: SimConfig | None = None
) -> Play:
    """Build a Play at home's kick-off with fresh streams derived from `seed`."""
    setup = setup or make_setup()
    root = SimRng(seed)
    state = build_state(setup, default_tables(), root.fork("dayform"))
    place_for_kickoff(state, "home")
    return Play(state, root.fork("play"), config or SimConfig(), EventEmitter(setup.match_id))
