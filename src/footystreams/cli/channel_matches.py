"""Matches for the channel: friendlies between two of the world's clubs, played by the simulator."""

from __future__ import annotations

import argparse
from pathlib import Path

from footystreams.cli.sim_world import WorldMatch, resolve_world_match
from footystreams.domain.match import MatchSetup
from footystreams.events.summary import MatchSummary
from footystreams.sim import SimConfig, run_match


class PreparedWorldMatch:
    """A fixture set up in the world, ready to be played."""

    def __init__(self, found: WorldMatch) -> None:
        """Hold the setup, tables and referee the simulator needs."""
        self._found = found

    @property
    def setup(self) -> MatchSetup:
        """The two teams and everything the simulator needs."""
        return self._found.setup

    def play(self, seed: int) -> MatchSummary:
        """Simulate the match for ``seed``; the same seed always gives the same match."""
        found = self._found
        return run_match(found.setup, seed, SimConfig(), found.tables, found.referee).summary


class WorldMatches:
    """Sets up fixtures from a world directory."""

    def __init__(self, world: Path) -> None:
        """Remember which world to draw clubs from."""
        self.world = world

    def prepare(self, home_id: str, away_id: str) -> PreparedWorldMatch:
        """Set up a friendly between two clubs, as of the world's date."""
        arguments = argparse.Namespace(home=home_id, away=away_id, world=self.world, db=None)
        return PreparedWorldMatch(resolve_world_match(arguments))
