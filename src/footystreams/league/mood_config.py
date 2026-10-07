"""Mood configuration models (``data/static/mood.yaml``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MoodCaps(_Config):
    """Hard caps on the multipliers; they bound the sum of all modifier sources."""

    mental_penalty: float = Field(ge=0.0, le=1.0)
    technical_penalty: float = Field(ge=0.0, le=1.0)
    physical_penalty: float = Field(ge=0.0, le=1.0)
    mental_bonus: float = Field(ge=0.0, le=1.0)
    technical_bonus: float = Field(ge=0.0, le=1.0)
    physical_bonus: float = Field(ge=0.0, le=1.0)
    volatility_add_max: float = Field(ge=0.0, le=1.0)


class KindEffect(_Config):
    """What one kind of modifier does per unit of strength."""

    mental: float
    technical: float
    physical: float
    volatility_add: float = Field(ge=0.0)
    default_days: int = Field(ge=1)
    decay: Literal["linear", "half_life"]
    half_life_days: int | None = None
    public: bool


class SensitivityWeights(_Config):
    """Trait weights shared by all kinds, split by the sign of the effect."""

    negative: dict[str, float]
    positive: dict[str, float]


class MoodConfig(_Config):
    """Everything in ``mood.yaml``."""

    caps: MoodCaps
    kinds: dict[str, KindEffect]
    sensitivity: SensitivityWeights
    kind_sensitivity: dict[str, dict[str, float]]
    sensitivity_floor: float = Field(gt=0.0)
    sensitivity_ceiling: float = Field(gt=0.0)
