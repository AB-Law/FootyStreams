"""Authored media personas (``data/static/media_archetypes.yaml``)."""

from __future__ import annotations

from pathlib import Path

from footystreams.domain.media import AgeRange, MediaRole, VoiceRegister
from footystreams.domain.types import Gender
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model

DISPOSITION_FIELDS = (
    "ambition", "loyalty", "professionalism", "volatility", "sportsmanship",
    "ego", "sociability", "humor", "media_openness", "resilience",
)  # fmt: skip


class VoiceYaml(YamlModel):
    """Casting sheet in the YAML."""

    age_range: AgeRange
    accent: str
    timbre: tuple[str, ...]
    voice_register: VoiceRegister
    base_pace_wpm: int
    pace_variance: float
    energy_range: tuple[float, float]
    delivery_notes: str


class CrewMember(YamlModel):
    """One authored persona."""

    role: MediaRole
    summary: str
    gender: dict[Gender, float]
    age: tuple[int, int]
    personality: dict[str, int]
    voice: VoiceYaml
    catchphrases: tuple[str, ...]
    expertise: tuple[str, ...]
    interjections: tuple[str, ...]


class MediaTables(YamlModel):
    """Everything in ``media_archetypes.yaml``."""

    distinctness_minimum: float
    crew: dict[str, CrewMember]


def load_media_tables(directory: Path | None = None) -> MediaTables:
    """Load the crew table; personalities must name exactly the ten disposition fields."""
    tables = load_model(MediaTables, "media_archetypes.yaml", directory)
    for key, member in tables.crew.items():
        if set(member.personality) != set(DISPOSITION_FIELDS):
            msg = (
                f"media_archetypes.yaml: {key!r} personality must set exactly {DISPOSITION_FIELDS}"
            )
            raise StaticDataError(msg)
    return tables
