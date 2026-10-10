"""Settings of one world generation run."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

GENERATOR_VERSION = "1.1.0"
WORLD_START = dt.date(2031, 7, 1)
MIN_CLUBS = 2
MAX_CLUBS = 8  # one club per archetype; a larger league needs more archetypes


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    """What to generate: how many clubs and the in-world date the world is created on."""

    clubs: int = MAX_CLUBS
    created_in_world: dt.date = WORLD_START

    def __post_init__(self) -> None:
        """Reject league sizes the archetype set cannot fill."""
        if not MIN_CLUBS <= self.clubs <= MAX_CLUBS:
            msg = f"clubs must be between {MIN_CLUBS} and {MAX_CLUBS}, got {self.clubs}"
            raise ValueError(msg)
