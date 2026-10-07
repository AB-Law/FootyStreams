"""The ``MatchSimulator`` seam and its implementations.

``MatchSimulator`` turns a frozen ``MatchSetup`` and a seed into a ``MatchResult``. Two
implementations satisfy it (and the same contract tests):

* ``ResultOnlySimulator`` - a deterministic score from team strength, mood, form and fatigue, with
  just enough events (goals, cards, injuries) for the league to run a season. It is also the
  production fallback when a real match fails verification (docs/design/10 section 7).
* ``EventSimulator`` - an adapter around the real simulator's ``run_match``. The function is
  injected by the composition root, so this layer never imports ``sim``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from footystreams.domain.attributes import attribute_map
from footystreams.domain.canonical import canonical_json
from footystreams.domain.match import MatchSetup, TeamSheet
from footystreams.domain.ratings import ability_from_attributes
from footystreams.domain.rng import WorldRng
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.events.result import MatchResult
from footystreams.league.config import ResultOnlyConfig
from footystreams.league.incidents import draw_side
from footystreams.league.result_events import Meta, build_result

RESULT_ONLY_VERSION = "result-only-1"
MOOD_WEIGHTS = (0.5, 0.3, 0.2)  # mental, technical, physical
MIN_EXPECTED_GOALS = 0.15
MAX_EXPECTED_GOALS = 5.0


class MatchSimulator(Protocol):
    """Anything that can play a match from a frozen setup."""

    def simulate(self, setup: MatchSetup, seed: int) -> MatchResult:
        """Play the match; the same setup and seed always give the same result."""


class EventSimulator:
    """Adapter that delegates to the real simulator's ``run_match`` (injected)."""

    def __init__(self, run_match: Callable[[MatchSetup, int], MatchResult]) -> None:
        """Wrap ``run_match``; the composition root passes the real function."""
        self._run_match = run_match

    def simulate(self, setup: MatchSetup, seed: int) -> MatchResult:
        """Delegate to the wrapped function."""
        return self._run_match(setup, seed)


def _flat(snapshot: PlayerSnapshot) -> dict[str, int]:
    merged: dict[str, int] = {}
    for group in (snapshot.technical, snapshot.mental, snapshot.physical, snapshot.goalkeeping):
        merged.update(attribute_map(group))
    return merged


@dataclass(frozen=True, slots=True)
class _Side:
    """One team's starters with their effective abilities."""

    sheet: TeamSheet
    starters: tuple[PlayerSnapshot, ...]
    strength: float


class ResultOnlySimulator:
    """Deterministic result-only simulator (see module docstring)."""

    def __init__(self, catalog: RoleCatalog, config: ResultOnlyConfig) -> None:
        """Create the simulator over a role catalogue and its tunables."""
        self._catalog = catalog
        self._config = config
        self.config_hash = hashlib.sha256(canonical_json(config.model_dump()).encode()).hexdigest()

    # ------------------------------------------------------------------ strength
    def _effective(self, snapshot: PlayerSnapshot) -> float:
        ability = ability_from_attributes(
            _flat(snapshot), snapshot.position_competence, self._catalog
        )
        mood = snapshot.mood
        mixed = (
            MOOD_WEIGHTS[0] * mood.mental_mult
            + MOOD_WEIGHTS[1] * mood.technical_mult
            + MOOD_WEIGHTS[2] * mood.physical_mult
        )
        config = self._config
        factor = (
            (1 + config.mood_gain * (mixed - 1))
            * (1 + config.form_weight * (snapshot.form - 0.5) * 2)
            * (1 - config.fatigue_weight * snapshot.fatigue)
        )
        return ability * factor

    def _side(self, sheet: TeamSheet) -> _Side:
        starters = tuple(sheet.squad[slot.player_id] for slot in sheet.lineup)
        strength = sum(self._effective(player) for player in starters) / len(starters)
        return _Side(sheet, starters, strength)

    def expected_goals(self, setup: MatchSetup) -> tuple[float, float]:
        """Expected goals for the home and away side."""
        home, away = self._side(setup.home), self._side(setup.away)
        config = self._config
        base = config.goals_per_match / 2
        swing = config.goals_per_rating_point * (home.strength - away.strength)
        low, high = MIN_EXPECTED_GOALS, MAX_EXPECTED_GOALS
        return (
            max(low, min(high, base + config.home_advantage / 2 + swing)),
            max(low, min(high, base - config.home_advantage / 2 - swing)),
        )

    # ------------------------------------------------------------------ the match
    def simulate(self, setup: MatchSetup, seed: int) -> MatchResult:
        """Play the match deterministically from ``seed``."""
        rng = WorldRng(seed).fork(f"result-only:{setup.match_id}")
        expected = self.expected_goals(setup)
        sides = (self._side(setup.home), self._side(setup.away))
        counts = tuple(self._goals(rng.fork(f"goals:{i}"), lam) for i, lam in enumerate(expected))
        drafts = [
            *draw_side(rng.fork("home"), "home", sides[0].starters, counts[0], self._config),
            *draw_side(rng.fork("away"), "away", sides[1].starters, counts[1], self._config),
        ]
        meta = Meta(RESULT_ONLY_VERSION, self.config_hash, self._config.rating_noise)
        return build_result(setup, seed, drafts, (meta, rng.fork("ratings")))

    def _goals(self, rng: WorldRng, expected: float) -> int:
        chances = self._config.goal_chances
        return sum(rng.bernoulli(expected / chances) for _ in range(chances))
