"""Formations, traits and injury types: tables that map one-to-one onto domain models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from footystreams.domain.injury import InjurySeverity
from footystreams.domain.static_tables import (
    Formation,
    FormationCatalog,
    FormationSlot,
    InjuryCatalog,
    InjuryType,
    TraitCatalog,
    TraitDefinition,
)
from footystreams.domain.types import FormationId, Position, TraitId
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model


class _FormationYaml(YamlModel):
    label: str
    slots: tuple[tuple[Position, float, float], ...]


class _FormationsFile(YamlModel):
    formations: dict[str, _FormationYaml]


class _TraitYaml(YamlModel):
    label: str
    usage: Literal["S", "R"]
    positions: tuple[Position, ...] = ()
    weight: float = Field(default=1.0, gt=0.0)


class _TraitsFile(YamlModel):
    traits: dict[str, _TraitYaml]


class _InjuryYaml(YamlModel):
    label: str
    body_part: str
    severity: InjurySeverity
    min_days: int
    max_days: int
    weight: float
    recurrence: float = 0.0


class _InjuriesFile(YamlModel):
    injuries: dict[str, _InjuryYaml]


def load_formations(directory: Path | None = None) -> FormationCatalog:
    """Load ``formations.yaml``; every formation must pass the domain slot validators."""
    raw = load_model(_FormationsFile, "formations.yaml", directory)
    formations: dict[FormationId, Formation] = {}
    for key, item in raw.formations.items():
        slots = tuple(
            FormationSlot(slot=index, position=position, x=x, y=y)
            for index, (position, x, y) in enumerate(item.slots)
        )
        try:
            formations[FormationId(key)] = Formation(
                id=FormationId(key), label=item.label, slots=slots
            )
        except ValueError as error:
            msg = f"formations.yaml: formation {key!r}: {error}"
            raise StaticDataError(msg) from error
    return FormationCatalog(formations=formations)


def load_traits(directory: Path | None = None) -> TraitCatalog:
    """Load ``traits.yaml``."""
    raw = load_model(_TraitsFile, "traits.yaml", directory)
    return TraitCatalog(
        traits={
            TraitId(key): TraitDefinition(
                id=TraitId(key),
                label=item.label,
                usage=item.usage,
                positions=item.positions,
                weight=item.weight,
            )
            for key, item in raw.traits.items()
        }
    )


def load_injuries(directory: Path | None = None) -> InjuryCatalog:
    """Load ``injuries.yaml``; every severity must have at least one injury type."""
    raw = load_model(_InjuriesFile, "injuries.yaml", directory)
    catalog = InjuryCatalog(
        injuries={
            key: InjuryType(id=key, **item.model_dump()) for key, item in raw.injuries.items()
        }
    )
    missing = [s.value for s in InjurySeverity if not catalog.of_severity(s)]
    if missing:
        msg = f"injuries.yaml has no injury type for severity: {', '.join(missing)}"
        raise StaticDataError(msg)
    return catalog
