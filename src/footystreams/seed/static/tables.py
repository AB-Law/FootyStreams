"""All static tables the seed generators need, loaded once and passed explicitly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import FormationCatalog, InjuryCatalog, TraitCatalog
from footystreams.seed.clubs.archetypes import ClubTables, load_club_tables
from footystreams.seed.managers.styles import StyleTables, load_styles
from footystreams.seed.media_tables import MediaTables, load_media_tables
from footystreams.seed.players.archetypes import ArchetypeTables, load_archetypes
from footystreams.seed.static.presets import PresetTables, load_presets
from footystreams.seed.static.roles import load_roles
from footystreams.seed.static.simple_tables import load_formations, load_injuries, load_traits


@dataclass(frozen=True, slots=True)
class StaticTables:
    """Hand-authored tables: roles, formations, traits, injuries, archetypes, styles and presets."""

    roles: RoleCatalog
    formations: FormationCatalog
    traits: TraitCatalog
    injuries: InjuryCatalog
    archetypes: ArchetypeTables
    styles: StyleTables
    presets: PresetTables
    clubs: ClubTables
    media: MediaTables


def load_static_tables(directory: Path | None = None) -> StaticTables:
    """Load and cross-check every static table."""
    roles = load_roles(directory)
    formations = load_formations(directory)
    return StaticTables(
        roles=roles,
        formations=formations,
        traits=load_traits(directory),
        injuries=load_injuries(directory),
        archetypes=load_archetypes(directory),
        styles=load_styles(directory),
        presets=load_presets(roles, formations, directory),
        clubs=load_club_tables(directory),
        media=load_media_tables(directory),
    )
