"""Development configuration models (``data/static/development.yaml``)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AgeCurve(_Config):
    """Expected yearly points by age: growth while young, decline when old."""

    growth: tuple[tuple[int, float], ...]
    decline: tuple[tuple[int, float], ...]

    def growth_at(self, age: int) -> float:
        """Points of growth per year at ``age``."""
        return _lookup(self.growth, age)

    def decline_at(self, age: int) -> float:
        """Points of decline per year at ``age``."""
        return _lookup(self.decline, age)


def _lookup(rows: tuple[tuple[int, float], ...], age: int) -> float:
    return next(value for bound, value in rows if age <= bound)


class ProgressionConfig(_Config):
    """How attributes move."""

    headroom_reference: int = Field(ge=1)
    micro_share: float = Field(ge=0.0, le=1.0)
    noise: float = Field(ge=0.0)
    default_playing_time: float = Field(ge=0.0, le=1.0)
    full_playing_time_minutes: float = Field(gt=0.0, le=1.0)
    training_floor: float = Field(ge=0.0, le=1.0)
    playing_time_floor: float = Field(ge=0.0, le=1.0)
    facility_weight: float = Field(ge=0.0, le=1.0)
    professionalism_weight: float
    development_rate_weight: float
    fitness_decline_weight: float
    injury_setback_max: int = Field(ge=0)
    curves: dict[str, AgeCurve]


class PotentialConfig(_Config):
    """Yearly revision of potential for young players."""

    min_age: int
    max_age: int
    chance: float = Field(ge=0.0, le=1.0)
    up: tuple[int, int]
    down: tuple[int, int]


class PositionConfig(_Config):
    """Position competence and role familiarity."""

    retrain_gain_per_year: int
    unused_decay_per_year: int
    role_familiarity_gain_per_year: int


class RetirementConfig(_Config):
    """Retirement hazard by age."""

    hazard: tuple[tuple[int, float], ...]
    ability_weight: float = Field(ge=0.0)
    min_hazard_multiplier: float = Field(ge=0.0)

    def hazard_at(self, age: int) -> float:
        """Base yearly retirement chance at ``age``."""
        return _lookup(self.hazard, age)


class YouthConfig(_Config):
    """Academy intake and promotion."""

    intake_age: tuple[int, int]
    ability_fraction: float = Field(gt=0.0, le=1.0)
    potential_bonus_base: int
    potential_bonus_per_quality: int
    contract_years: int = Field(ge=1)
    promotion_age: int
    max_age: int
    promotion_margin: int
    potential_weight: float = Field(ge=0.0, le=1.0)
    wage_weekly: int = Field(ge=0)


class SquadConfig(_Config):
    """Squad-size rules."""

    min_senior: int
    max_senior: int
    min_goalkeepers: int
    trialist_contract_years: int = Field(ge=1)
    free_agent_pool: int = Field(ge=0)
    free_agent_pool_max: int = Field(ge=0)
    journeyman_age: tuple[int, int]
    journeyman_ability_fraction: float = Field(gt=0.0, le=1.0)


class RolloverConfig(_Config):
    """The off-season steps outside development: reputation, money, contracts, awards."""

    reputation_step: float
    reputation_max_change: int = Field(ge=0)
    player_reputation_pull: float = Field(ge=0.0, le=1.0)
    player_reputation_ability_weight: float = Field(ge=0.0, le=1.0)
    fanbase_drift: float = Field(ge=0.0)
    confidence_step: float = Field(ge=0.0)
    sponsor_years: tuple[int, int]
    sponsor_reputation_growth: float
    wage_budget_ratio: float = Field(gt=0.0)
    wage_tolerance: float = Field(ge=0.0)
    wage_scale_max: float = Field(ge=1.0)
    transfer_budget_share: float = Field(ge=0.0, le=1.0)
    contract_extend_years: tuple[int, int]
    awards_min_appearances: int = Field(ge=1)


class DevelopmentConfig(_Config):
    """Everything in ``development.yaml``."""

    progression: ProgressionConfig
    potential: PotentialConfig
    positions: PositionConfig
    retirement: RetirementConfig
    youth: YouthConfig
    squad: SquadConfig
    rollover: RolloverConfig
