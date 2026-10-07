"""Noisy scouting: a club judges a player with an error that shrinks as its judgement improves."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.league.transfer_config import ScoutingConfig

JUDGING_SCALE = 100.0
ABILITY_MIN, ABILITY_MAX = 1, 100


@dataclass(frozen=True, slots=True)
class Perception:
    """What a club believes about a player."""

    ability: int
    potential: int
    confidence: float


def noise_sigma(judging: int, config: ScoutingConfig) -> float:
    """Standard deviation of the ability estimate: full noise at judging 0, none at 100."""
    return config.noise_at_zero_judging * (1.0 - judging / JUDGING_SCALE)


def perceive(player: Player, judging: int, config: ScoutingConfig, rng: WorldRng) -> Perception:
    """The club's estimate of the player; potential is judged more noisily than ability."""
    sigma = noise_sigma(judging, config)
    ability = player.ability_current + round(rng.fork("ability").normal(0.0, sigma))
    potential = player.ability_potential + round(
        rng.fork("potential").normal(0.0, sigma * config.potential_factor)
    )
    confidence = max(config.confidence_floor, judging / JUDGING_SCALE)
    ability = _clamp(ability)
    return Perception(
        ability=ability, potential=max(ability, _clamp(potential)), confidence=round(confidence, 4)
    )


def _clamp(value: int) -> int:
    return max(ABILITY_MIN, min(ABILITY_MAX, value))
