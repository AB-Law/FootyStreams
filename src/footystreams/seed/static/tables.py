"""All static tables the seed generators need, loaded once and passed explicitly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import FormationCatalog, InjuryCatalog, TraitCatalog
from footystreams.seed.players.archetypes import ArchetypeTables, load_archetypes
from footystreams.seed.static.roles import load_roles
from footystreams.seed.static.simple_tables import load_formations, load_injuries, load_traits


@dataclass(frozen=True, slots=True)
class StaticTables:
    """Hand-authored tables: roles, formations, traits, injuries and player archetypes."""

    roles: RoleCatalog
    formations: FormationCatalog
    traits: TraitCatalog
    injuries: InjuryCatalog
    archetypes: ArchetypeTables


def load_static_tables(directory: Path | None = None) -> StaticTables:
    """Load and cross-check every static table."""
    return StaticTables(
        roles=load_roles(directory),
        formations=load_formations(directory),
        traits=load_traits(directory),
        injuries=load_injuries(directory),
        archetypes=load_archetypes(directory),
    )
