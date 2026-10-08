"""Load the committed league and mood tables for tests (the real composition does the same)."""

from __future__ import annotations

from functools import cache

from footystreams.league.config import LeagueConfig
from footystreams.league.development_config import DevelopmentConfig
from footystreams.league.mood_config import MoodConfig
from footystreams.seed.static.files import read_yaml


@cache
def make_league_config() -> LeagueConfig:
    """The committed ``data/static/league.yaml``."""
    return LeagueConfig.model_validate(read_yaml("league.yaml"))


@cache
def make_mood_config() -> MoodConfig:
    """The committed ``data/static/mood.yaml``."""
    return MoodConfig.model_validate(read_yaml("mood.yaml"))


@cache
def make_development_config() -> DevelopmentConfig:
    """The committed ``data/static/development.yaml``."""
    return DevelopmentConfig.model_validate(read_yaml("development.yaml"))
