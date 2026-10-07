"""Position competence, role familiarity and traits for a generated player."""

from __future__ import annotations

from collections.abc import Mapping

from footystreams.domain.rng import WorldRng
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import TraitCatalog
from footystreams.domain.types import Duty, Position, RoleAssignment, RoleId, TraitId
from footystreams.seed.players.archetypes import ArchetypeTables, PlayerArchetype

NATURAL_COMPETENCE = (92, 100)
YOUTH_NATURAL_COMPETENCE = (84, 96)
KEEPER_IN_OUTFIELD = (3, 12)
MIN_KEPT_COMPETENCE = 20
VERSATILITY_FLOOR = 0.9  # a player with no versatility keeps this share of the adjacency value
VERSATILITY_SPAN = 0.1
PERCENT = 100.0
PREFERRED_FAMILIARITY = (75, 100)
OTHER_FAMILIARITY = (20, 55)
FAMILIARITY_POSITION_FLOOR = 60
TRAIT_ADOPTION_CHANCE = 0.55
EXTRA_TRAITS = {0: 5.0, 1: 3.0, 2: 2.0}
MAX_PREFERRED_ROLES = 4


def position_competence(
    rng: WorldRng,
    tables: ArchetypeTables,
    natural: Position,
    versatility: int,
    *,
    youth: bool,
) -> dict[Position, int]:
    """Natural position 92-100, related positions by the adjacency graph scaled by versatility."""
    low, high = YOUTH_NATURAL_COMPETENCE if youth else NATURAL_COMPETENCE
    base = rng.randint(low, high)
    result = {natural: base}
    scale = VERSATILITY_FLOOR + VERSATILITY_SPAN * versatility / PERCENT
    for related, adjacency in sorted(tables.adjacency[natural].items()):
        value = round(adjacency * scale * base / PERCENT)
        if value >= MIN_KEPT_COMPETENCE:
            result[related] = value
    if natural is not Position.GK:
        result[Position.GK] = rng.randint(*KEEPER_IN_OUTFIELD)
    return result


def resolve_role(catalog: RoleCatalog, base: str, position: Position) -> RoleId:
    """Role id for a YAML role name at a position (exact id, else the per-position expansion)."""
    exact = RoleId(base)
    if exact in catalog.roles:
        return exact
    expanded = RoleId(f"{base}_{position.value.lower()}")
    if expanded in catalog.roles:
        return expanded
    msg = f"archetype role {base!r} has no role id for position {position.value}"
    raise ValueError(msg)


def preferred_roles(catalog: RoleCatalog, archetype: PlayerArchetype) -> tuple[RoleAssignment, ...]:
    """The archetype's at-home roles as assignments (at most four)."""
    assignments: list[RoleAssignment] = []
    for entry in archetype.roles[:MAX_PREFERRED_ROLES]:
        base, _, duty = entry.partition(":")
        role_id = resolve_role(catalog, base, archetype.position)
        assignments.append(RoleAssignment(role_id=role_id, duty=Duty(duty)))
    return tuple(assignments)


def role_familiarity(
    rng: WorldRng,
    catalog: RoleCatalog,
    competence: Mapping[Position, int],
    preferred: tuple[RoleAssignment, ...],
) -> dict[RoleId, int]:
    """High familiarity for preferred roles, modest for other roles he is competent to play."""
    result: dict[RoleId, int] = {}
    for role_id, role in sorted(catalog.roles.items()):
        if competence.get(role.position, 0) >= FAMILIARITY_POSITION_FLOOR:
            result[role_id] = rng.randint(*OTHER_FAMILIARITY)
    for assignment in preferred:
        result[assignment.role_id] = rng.randint(*PREFERRED_FAMILIARITY)
    return result


def choose_traits(
    rng: WorldRng, catalog: TraitCatalog, archetype: PlayerArchetype
) -> tuple[TraitId, ...]:
    """Traits typical of the archetype plus a few random ones plausible for the position."""
    chosen: list[TraitId] = [
        TraitId(name)
        for name in archetype.traits
        if TraitId(name) in catalog.traits and rng.bernoulli(TRAIT_ADOPTION_CHANCE)
    ]
    extra = rng.choice_weighted(EXTRA_TRAITS)
    eligible = {
        trait_id: trait.weight
        for trait_id, trait in sorted(catalog.traits.items())
        if trait_id not in chosen and (not trait.positions or archetype.position in trait.positions)
    }
    for _ in range(extra):
        if not eligible:
            break
        picked = rng.choice_weighted(eligible)
        chosen.append(picked)
        del eligible[picked]
    return tuple(chosen)
