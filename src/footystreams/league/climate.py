"""Climate bands (``data/static/climate.yaml``): what weather a city can have, by month."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

MONTHS = 12


class ClimateBand(BaseModel):
    """Typical weather of one band; ``monthly_temp_c`` runs January to December."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    monthly_temp_c: tuple[float, ...]
    rain_probability: float = Field(ge=0.0, le=1.0)
    wind_mean_mps: float = Field(ge=0.0)
    humidity: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _twelve_months(self) -> ClimateBand:
        if len(self.monthly_temp_c) != MONTHS:
            msg = f"monthly_temp_c needs {MONTHS} values, got {len(self.monthly_temp_c)}"
            raise ValueError(msg)
        return self


class ClimateCatalog(BaseModel):
    """All bands by key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bands: dict[str, ClimateBand]
