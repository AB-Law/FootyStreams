"""Club archetype tables (``data/static/club_archetypes.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from footystreams.domain.manager import ObjectiveKind
from footystreams.domain.types import Position
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model

IntRange = tuple[int, int]
FloatRange = tuple[float, float]


class LeagueSpec(YamlModel):
    """The league and its structural targets."""

    name: str
    short_name: str
    first_season_label: str
    season_start: str
    season_end: str
    min_gap: float
    max_gap: float
    min_adjacent_gap: float
    calibration_tolerance: float


class SquadSpec(YamlModel):
    """Squad composition and ability-shaping parameters."""

    senior_template: dict[Position, int]
    youth_positions: tuple[Position, ...]
    age_mean: float
    age_deviation: float
    age_range: IntRange
    goalkeeper_age_bonus: int
    home_players: IntRange
    foreign_nations: IntRange
    max_per_foreign_nation: int
    youth_age_range: IntRange
    youth_ability: IntRange
    starter_noise: float
    second_choice_drop: IntRange
    deep_drop: IntRange
    free_agents: int
    free_agent_ability: IntRange
    free_agent_age: IntRange


class Palette(YamlModel):
    """A club colour trio."""

    primary: str
    secondary: str
    accent: str


class StadiumSpecYaml(YamlModel):
    """Ranges for a stadium."""

    capacity: IntRange
    pitch_quality: FloatRange
    atmosphere: FloatRange
    proximity: FloatRange
    surface: Literal["grass", "hybrid", "artificial"]
    length: IntRange
    width: IntRange


class FanbaseSpecYaml(YamlModel):
    """Ranges for a fanbase."""

    size_k: IntRange
    passion: FloatRange
    toxicity: FloatRange
    fickleness: FloatRange
    away_following: FloatRange


class ObjectiveSpec(YamlModel):
    """The board's main objective for the first season."""

    kind: ObjectiveKind
    target: str


class BoardSpecYaml(YamlModel):
    """Ranges for a board."""

    ambition: IntRange
    patience: IntRange
    meddling: IntRange
    budget_strictness: IntRange
    objective: ObjectiveSpec


class FacilitiesSpecYaml(YamlModel):
    """Ranges for facilities and academy intake."""

    training: IntRange
    youth: IntRange
    medical: IntRange
    intake: IntRange


class ClubArchetype(YamlModel):
    """One of the eight club archetypes."""

    drama: str
    reputation: IntRange
    quality: FloatRange
    style_weights: dict[str, float]
    city_percentile: float = Field(ge=0.0, le=1.0)
    income_m: IntRange
    wage_budget_share: FloatRange
    wage_ratio: FloatRange
    transfer_budget_m: IntRange
    balance_m: IntRange
    debt_m: IntRange
    stadium: StadiumSpecYaml
    fanbase: FanbaseSpecYaml
    board: BoardSpecYaml
    facilities: FacilitiesSpecYaml
    founded: IntRange
    academy_bonus: int
    young_squad: bool
    nicknames: tuple[str, ...]
    culture_tags: tuple[str, ...]


class RivalrySpec(YamlModel):
    """A derby or rivalry between two archetypes."""

    a: str
    b: str
    intensity: float
    label: str
    origin: str


class ClubTables(YamlModel):
    """Everything in ``club_archetypes.yaml``."""

    league: LeagueSpec
    squad: SquadSpec
    shirt_numbers: dict[Position, tuple[int, ...]]
    palettes: tuple[Palette, ...]
    kit_patterns: dict[str, float]
    club_suffixes: tuple[str, ...]
    stadium_suffixes: tuple[str, ...]
    crest_symbols: tuple[str, ...]
    crest_decorations: tuple[str, ...]
    sponsors: tuple[str, ...]
    archetypes: dict[str, ClubArchetype]
    rivalries: tuple[RivalrySpec, ...]


def load_club_tables(directory: Path | None = None) -> ClubTables:
    """Load and cross-check: rivalries name real archetypes, palettes cover the league."""
    tables = load_model(ClubTables, "club_archetypes.yaml", directory)
    for rivalry in tables.rivalries:
        for key in (rivalry.a, rivalry.b):
            if key not in tables.archetypes:
                msg = f"club_archetypes.yaml: rivalry names unknown archetype {key!r}"
                raise StaticDataError(msg)
    if len(tables.palettes) < len(tables.archetypes):
        msg = "club_archetypes.yaml: need at least one palette per archetype"
        raise StaticDataError(msg)
    return tables
