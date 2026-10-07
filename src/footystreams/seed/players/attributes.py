"""Spiky attribute sets whose role-weighted ability hits a target.

Each attribute is ``level + offset``: the offset (archetype bias, position bias, correlated latent
factors and noise) fixes the *shape* of the player, and a single integer ``level`` is solved so the
domain's own ability formula returns the target. The generator therefore never has its own idea
of "how good" a player is; ``ability_from_attributes`` stays the one source of truth.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from footystreams.domain.attributes import (
    GoalkeepingAttrs,
    MentalAttrs,
    PhysicalAttrs,
    TechnicalAttrs,
)
from footystreams.domain.ratings import ability_from_attributes
from footystreams.domain.rng import WorldRng
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.types import Position
from footystreams.seed.players.archetypes import ArchetypeTables, PlayerArchetype
from footystreams.seed.static.tables import StaticTables

LEVEL_FLOOR = -60
LEVEL_CEILING = 100
ATTRIBUTE_MIN = 1
ATTRIBUTE_MAX = 100
OUTFIELD_KEEPING_RANGE = (5, 20)
OUTFIELD_GROUPS = (TechnicalAttrs, MentalAttrs, PhysicalAttrs)


@dataclass(frozen=True, slots=True)
class AttributeSet:
    """The four skill groups of a player plus the ability they produce."""

    technical: TechnicalAttrs
    mental: MentalAttrs
    physical: PhysicalAttrs
    goalkeeping: GoalkeepingAttrs
    ability: int
    aggression: int


def _clamp(value: float) -> int:
    return max(ATTRIBUTE_MIN, min(ATTRIBUTE_MAX, round(value)))


def sample_offsets(
    rng: WorldRng, tables: ArchetypeTables, archetype: PlayerArchetype
) -> dict[str, float]:
    """Per-attribute offsets from the level: position bias + archetype bias + latent + noise."""
    latent = tables.latent
    factors = {name: rng.normal(0.0, latent.factor_deviation) for name in sorted(latent.loadings)}
    position_bias = tables.position_bias[archetype.position]
    names = [name for group in (*OUTFIELD_GROUPS, GoalkeepingAttrs) for name in group.model_fields]
    offsets: dict[str, float] = {}
    for name in names:
        shared = sum(
            loadings.get(name, 0.0) * factors[factor]
            for factor, loadings in sorted(latent.loadings.items())
        )
        offsets[name] = (
            position_bias.get(name, 0.0)
            + archetype.bias.get(name, 0.0)
            + shared
            + rng.normal(0.0, latent.noise_deviation)
        )
    return offsets


def _attributes_at(
    level: int, offsets: Mapping[str, float], fixed: Mapping[str, int]
) -> dict[str, int]:
    attributes = {name: _clamp(level + offset) for name, offset in offsets.items()}
    attributes.update(fixed)
    return attributes


def solve_level(
    offsets: Mapping[str, float],
    fixed: Mapping[str, int],
    competence: Mapping[Position, int],
    catalog: RoleCatalog,
    target_ability: int,
) -> int:
    """Smallest-error integer level whose attribute set scores ``target_ability``."""

    def ability(level: int) -> int:
        return ability_from_attributes(_attributes_at(level, offsets, fixed), competence, catalog)

    low, high = LEVEL_FLOOR, LEVEL_CEILING
    while low < high:
        middle = (low + high) // 2
        if ability(middle) < target_ability:
            low = middle + 1
        else:
            high = middle
    below = max(LEVEL_FLOOR, low - 1)
    return (
        below if abs(ability(below) - target_ability) < abs(ability(low) - target_ability) else low
    )


def _group[T: (TechnicalAttrs, MentalAttrs, PhysicalAttrs, GoalkeepingAttrs)](
    model: type[T], values: Mapping[str, int]
) -> T:
    return model(**{name: values[name] for name in model.model_fields})


@dataclass(frozen=True, slots=True)
class AttributeBrief:
    """What the attribute generator is asked for: a shape, the positions he can play, a target."""

    archetype: PlayerArchetype
    competence: Mapping[Position, int]
    target_ability: int


def generate_attributes(rng: WorldRng, tables: StaticTables, brief: AttributeBrief) -> AttributeSet:
    """Draw a spiky attribute set for the brief's archetype whose ability matches its target."""
    offsets = sample_offsets(rng.fork("offsets"), tables.archetypes, brief.archetype)
    fixed: dict[str, int] = {}
    if brief.archetype.position is not Position.GK:
        keeping = rng.fork("keeping")
        fixed = {
            name: keeping.randint(*OUTFIELD_KEEPING_RANGE) for name in GoalkeepingAttrs.model_fields
        }
        offsets = {name: offset for name, offset in offsets.items() if name not in fixed}
    level = solve_level(offsets, fixed, brief.competence, tables.roles, brief.target_ability)
    values = _attributes_at(level, offsets, fixed)
    return AttributeSet(
        technical=_group(TechnicalAttrs, values),
        mental=_group(MentalAttrs, values),
        physical=_group(PhysicalAttrs, values),
        goalkeeping=_group(GoalkeepingAttrs, values),
        ability=ability_from_attributes(values, brief.competence, tables.roles),
        aggression=values["aggression"],
    )
