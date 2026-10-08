"""League-layer configuration models (``data/static/league.yaml``); pure data, no I/O."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

MonthDay = Annotated[tuple[int, int], Field(description="(month, day)")]


class _Config(BaseModel):
    """Frozen, strict base of every config block."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CalendarConfig(_Config):
    """Season shape: start and end, matchday spacing, transfer windows, contract end day."""

    season_start: MonthDay
    season_end: MonthDay
    matchday_spacing_days: int = Field(ge=1)
    midseason_window_after_matchday: int = Field(ge=1)
    midseason_window_days: int = Field(ge=1)
    summer_window_open: MonthDay
    summer_window_close: MonthDay
    contract_end: MonthDay

    def season_start_in(self, year: int) -> dt.date:
        """First matchday of the season that starts in ``year``."""
        return dt.date(year, *self.season_start)

    def season_end_in(self, start_year: int) -> dt.date:
        """Last day of the season that started in ``start_year`` (next calendar year)."""
        return dt.date(start_year + 1, *self.season_end)


class FinanceConfig(_Config):
    """Income and expense parameters."""

    weeks_per_year: int = Field(ge=1)
    home_matches_per_season: int = Field(ge=1)
    hospitality_share_of_gate: float = Field(ge=0.0)
    merchandise_per_fan_per_season: float = Field(ge=0.0)
    merchandise_form_weight: float = Field(ge=0.0, le=1.0)
    facilities_upkeep_per_level_week: int = Field(ge=0)
    youth_academy_per_level_week: int = Field(ge=0)
    ticket_price_scale: float = Field(gt=0.0)
    pay_weekday: int = Field(ge=0, le=6)
    prize_pool_share_of_broadcast: float = Field(ge=0.0)
    prize_position_decay: float = Field(gt=0.0, lt=1.0)
    broadcast_merit_share: float = Field(ge=0.0, le=1.0)
    merchandise_outcome_factor: dict[str, float]


class AttendanceConfig(_Config):
    """How full the ground is."""

    base_fill: float = Field(ge=0.0, le=1.0)
    reputation_weight: float
    form_weight: float
    derby_bonus: float
    bad_weather_penalty: float
    fickleness_weight: float
    noise: float = Field(ge=0.0)
    minimum_fill: float = Field(ge=0.0, le=1.0)


class WeatherConfig(_Config):
    """Weather generation thresholds."""

    rain_temperature_limit: float
    hot_threshold: float
    cold_threshold: float
    kickoff_hours: tuple[int, ...]
    night_hour: int
    temperature_noise: float = Field(ge=0.0)
    wind_noise: float = Field(ge=0.0)


class RecoveryConfig(_Config):
    """Daily recovery and post-match condition changes."""

    fatigue_rest_day: float = Field(ge=0.0)
    fitness_gain_rest_day: float = Field(ge=0.0)
    sharpness_decay_idle_week: float = Field(ge=0.0)
    sharpness_floor: float = Field(ge=0.0, le=1.0)
    sharpness_gain_per_match: float = Field(ge=0.0)
    morale_drift_per_day: float = Field(ge=0.0)
    morale_win: float
    morale_loss: float
    form_weight_new_rating: float = Field(ge=0.0, le=1.0)
    injury_day_per_medical_level: float = Field(ge=0.0)
    suspension_yellow_threshold: int = Field(ge=1)
    fatigue_per_match_minute: float = Field(ge=0.0)
    rotation_fatigue_threshold: float = Field(ge=0.0, le=1.0)
    rotation_ability_margin: int = Field(ge=0)
    red_card_ban_matches: int = Field(ge=1)
    injury_severity_weights: dict[str, float]


class WorldEventsConfig(_Config):
    """The seeded life-event generator."""

    daily_hazard: float = Field(ge=0.0, le=1.0)
    roll_interval_days: int = Field(ge=1)
    volatility_weight: float
    media_weight: float
    kind_weights: dict[str, float]
    duration_days: tuple[int, int]
    magnitude: tuple[float, float]


class ResultOnlyConfig(_Config):
    """Parameters of the result-only match simulator."""

    goals_per_match: float = Field(gt=0.0)
    home_advantage: float
    goals_per_rating_point: float = Field(ge=0.0)
    mood_gain: float = Field(ge=0.0)
    form_weight: float
    fatigue_weight: float
    goal_chances: int = Field(ge=1)
    yellow_chance: float = Field(ge=0.0, le=1.0)
    red_chance: float = Field(ge=0.0, le=1.0)
    injury_chance: float = Field(ge=0.0, le=1.0)
    rating_noise: float = Field(ge=0.0)


class LeagueConfig(_Config):
    """Everything the league layer reads from ``league.yaml``."""

    calendar: CalendarConfig
    finance: FinanceConfig
    attendance: AttendanceConfig
    weather: WeatherConfig
    recovery: RecoveryConfig
    world_events: WorldEventsConfig
    result_only: ResultOnlyConfig
