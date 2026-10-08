"""Player archetype tables (``data/static/player_archetypes.yaml``)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from footystreams.domain.types import Position
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model


class LatentSpec(YamlModel):
    """Correlated latent factors that move related attributes together."""

    factor_deviation: float
    noise_deviation: float
    loadings: dict[str, dict[str, float]]


class AppearanceSpec(YamlModel):
    """Weighted appearance choices."""

    skin_tone: dict[int, float]
    hair_style: dict[str, float]
    hair_colour: dict[str, float]
    facial_hair: dict[str, float]
    build: dict[str, float]


class PlayerArchetype(YamlModel):
    """One kind of player at a natural position."""

    position: Position
    weight: float = Field(gt=0.0)
    bias: dict[str, float]
    roles: tuple[str, ...]
    traits: tuple[str, ...] = ()
    height: tuple[float, float]
    bmi: tuple[float, float]


class ArchetypeTables(YamlModel):
    """Everything in ``player_archetypes.yaml``."""

    latent: LatentSpec
    position_bias: dict[Position, dict[str, float]]
    adjacency: dict[Position, dict[Position, float]]
    appearance: AppearanceSpec
    archetypes: dict[str, PlayerArchetype]

    def for_position(self, position: Position) -> dict[str, float]:
        """Archetype keys of one natural position with their frequency weights."""
        return {
            key: item.weight for key, item in self.archetypes.items() if item.position is position
        }


def load_archetypes(directory: Path | None = None) -> ArchetypeTables:
    """Load the table and check every position has an archetype and a bias row."""
    tables = load_model(ArchetypeTables, "player_archetypes.yaml", directory)
    missing = [pos.value for pos in Position if not tables.for_position(pos)]
    if missing:
        msg = f"player_archetypes.yaml: no archetype for position(s) {', '.join(missing)}"
        raise StaticDataError(msg)
    no_bias = [pos.value for pos in Position if pos not in tables.position_bias]
    if no_bias:
        msg = f"player_archetypes.yaml: no position_bias for {', '.join(no_bias)}"
        raise StaticDataError(msg)
    return tables
