"""Static tables the simulation reads: formations (and, optionally, the role catalogue).

The sim never loads files. Tables are built by the composition root and passed in; `default_tables`
ships the eight standard formations so the sim runs before the YAML loaders of M2 exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from footystreams.domain.roles import RoleCatalog
from footystreams.domain.types import FormationId, Position
from footystreams.sim.formations import BUILTIN_FORMATIONS


@dataclass(frozen=True, slots=True)
class FormationSlot:
    """One of the eleven positions of a formation, in attack-normalised coordinates.

    `x` runs from 0 (own goal line) to 1 (opponent goal line); `y` from 0 (left touchline as the
    team faces the opponent) to 1 (right touchline).
    """

    position: Position
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Formation:
    """A named arrangement of eleven slots; slot 0 is always the goalkeeper."""

    formation_id: FormationId
    slots: tuple[FormationSlot, ...]


@dataclass(frozen=True, slots=True)
class StaticTables:
    """Everything static the simulation needs besides the setup and the config."""

    formations: Mapping[FormationId, Formation]
    roles: RoleCatalog | None = None


def default_tables() -> StaticTables:
    """Return tables holding the built-in formations and no role catalogue."""
    formations = {
        FormationId(name): Formation(
            FormationId(name), tuple(FormationSlot(Position(code), x, y) for code, x, y in rows)
        )
        for name, rows in BUILTIN_FORMATIONS.items()
    }
    return StaticTables(formations=formations)
