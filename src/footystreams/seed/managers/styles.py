"""Manager style prototypes and specialisms (``data/static/manager_styles.yaml``)."""

from __future__ import annotations

from pathlib import Path

from footystreams.domain.manager import ManagerStyle
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model


class SubstitutionRanges(YamlModel):
    """Ranges the substitution habits are drawn from."""

    earliest_minute: tuple[int, int]
    aggressiveness: tuple[float, float]
    protect_lead_bias: tuple[float, float]
    chase_game_bias: tuple[float, float]


class StylePrototype(YamlModel):
    """One style: the tactic preset it starts from, philosophy centres and weighted choices."""

    preset: str
    philosophy: dict[str, float]
    formations: dict[str, float]
    press_tones: dict[str, float]
    touchline: dict[str, float]
    substitutions: SubstitutionRanges


class StyleTables(YamlModel):
    """Everything in ``manager_styles.yaml``."""

    styles: dict[ManagerStyle, StylePrototype]
    specialisms: dict[str, dict[str, int]]


def load_styles(directory: Path | None = None) -> StyleTables:
    """Load the table; every ManagerStyle needs a prototype."""
    tables = load_model(StyleTables, "manager_styles.yaml", directory)
    missing = [style.value for style in ManagerStyle if style not in tables.styles]
    if missing:
        msg = f"manager_styles.yaml: no prototype for style(s) {', '.join(missing)}"
        raise StaticDataError(msg)
    return tables
