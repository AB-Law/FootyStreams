"""Name-culture grammar tables (``data/static/name_cultures.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from footystreams.seed.static.files import StaticDataError, YamlModel, load_model

Shape = Literal["root_suffix", "compound", "particle"]
Stress = Literal["first", "last", "penult"]
Kind = Literal["region", "nation"]
MAX_DIACRITIC_TYPES = 2


class GivenGrammar(YamlModel):
    """How given names are built: syllable count and gendered endings."""

    syllables: dict[int, float]
    male_endings: dict[str, float]
    female_endings: dict[str, float]


class SurnameGrammar(YamlModel):
    """How surnames are built: shape mix, roots, suffixes and particles."""

    shapes: dict[Shape, float]
    root_syllables: dict[int, float]
    suffixes: dict[str, float]
    particles: tuple[str, ...] = ()


class NameCulture(YamlModel):
    """One invented culture: a phoneme inventory plus given-name and surname grammars."""

    kind: Kind
    label: str
    onsets: dict[str, float]
    nuclei: dict[str, float]
    codas: dict[str, float]
    stress: Stress
    given: GivenGrammar
    surname: SurnameGrammar
    hyphen_share: float = Field(ge=0.0, le=1.0)
    diacritics: dict[str, str] = Field(default_factory=dict)
    diacritic_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _grammar_is_usable(self) -> NameCulture:
        if len(self.diacritics) > MAX_DIACRITIC_TYPES:
            msg = f"{self.label}: at most {MAX_DIACRITIC_TYPES} diacritic types"
            raise ValueError(msg)
        wants_particles = self.surname.shapes.get("particle", 0.0) > 0
        if wants_particles and not self.surname.particles:
            msg = f"{self.label}: particle shape needs particles"
            raise ValueError(msg)
        return self


class _CulturesFile(YamlModel):
    cultures: dict[str, NameCulture]


def load_cultures(directory: Path | None = None) -> dict[str, NameCulture]:
    """Load every culture; both regional and foreign cultures must exist."""
    cultures = load_model(_CulturesFile, "name_cultures.yaml", directory).cultures
    kinds = {culture.kind for culture in cultures.values()}
    if kinds != {"region", "nation"}:
        msg = "name_cultures.yaml needs both region and nation cultures"
        raise StaticDataError(msg)
    return cultures
