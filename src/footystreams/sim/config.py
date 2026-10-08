"""SimConfig: every tunable of the simulation, frozen, hashable and mergeable.

One group per concern (docs/design/02 section 14.6); groups are added by the milestone that
introduces the behaviour. `config_hash` identifies the exact numbers a match was played with.

Every numeric knob is bounded, so `merge_config` (the balance harness) cannot build a config the
simulator would divide by zero on. Structural constants that are not tuned per run (attribute
mixes, rating pivots, the threat surface) are named module constants: they are covered by
`SIM_VERSION`, not by `config_hash`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.canonical import canonical_json
from footystreams.sim.config_manager import ManagerConfig
from footystreams.sim.config_play import (
    ChallengeConfig,
    DecisionConfig,
    DribbleConfig,
    PassConfig,
    PositionConfig,
    PressureConfig,
    ShotConfig,
    TempoConfig,
)
from footystreams.sim.config_rules import (
    DisciplineConfig,
    OffsideConfig,
    RefereeConfig,
    RestartConfig,
    StoppageConfig,
)
from footystreams.sim.config_world import (
    FatigueConfig,
    HomeAdvantageConfig,
    InjuryConfig,
    WeatherConfig,
)

CONFIG_HASH_LENGTH = 16

__all__ = [
    "ChallengeConfig",
    "DecisionConfig",
    "DisciplineConfig",
    "DribbleConfig",
    "FatigueConfig",
    "HomeAdvantageConfig",
    "InjuryConfig",
    "ManagerConfig",
    "OffsideConfig",
    "PassConfig",
    "PositionConfig",
    "PressureConfig",
    "RefereeConfig",
    "RestartConfig",
    "ShotConfig",
    "SimConfig",
    "StoppageConfig",
    "TempoConfig",
    "WeatherConfig",
    "config_hash",
    "merge_config",
]


class SimConfig(DomainModel):
    """Top-level simulation configuration (defaults are the shipped balance).

    `emit_frames`, `frame_interval_s` and `home_advantage_scale` are reserved by the design
    (03 section 3, 02 section 11) and wired by M6/M7; until then they change `config_hash` only.
    """

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "model_profile": "S",
        "emit_frames": "S",
        "frame_interval_s": "S",
        "home_advantage_scale": "S",
        "positioning": "S",
        "pressure": "S",
        "passing": "S",
        "shot": "S",
        "dribble": "S",
        "decision": "S",
        "tempo": "S",
        "challenge": "S",
        "referee": "S",
        "discipline": "S",
        "restarts": "S",
        "offside": "S",
        "stoppage": "S",
        "weather": "S",
        "fatigue": "S",
        "home_advantage": "S",
        "injury": "S",
        "manager": "S",
    }

    model_profile: str = "v1"
    emit_frames: bool = False
    frame_interval_s: int = Field(ge=1, le=60, default=1)
    home_advantage_scale: float = Field(ge=0.0, le=3.0, default=1.0)
    positioning: PositionConfig = Field(default_factory=PositionConfig)
    pressure: PressureConfig = Field(default_factory=PressureConfig)
    passing: PassConfig = Field(default_factory=PassConfig)
    shot: ShotConfig = Field(default_factory=ShotConfig)
    dribble: DribbleConfig = Field(default_factory=DribbleConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)
    tempo: TempoConfig = Field(default_factory=TempoConfig)
    challenge: ChallengeConfig = Field(default_factory=ChallengeConfig)
    referee: RefereeConfig = Field(default_factory=RefereeConfig)
    discipline: DisciplineConfig = Field(default_factory=DisciplineConfig)
    restarts: RestartConfig = Field(default_factory=RestartConfig)
    offside: OffsideConfig = Field(default_factory=OffsideConfig)
    stoppage: StoppageConfig = Field(default_factory=StoppageConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    fatigue: FatigueConfig = Field(default_factory=FatigueConfig)
    home_advantage: HomeAdvantageConfig = Field(default_factory=HomeAdvantageConfig)
    injury: InjuryConfig = Field(default_factory=InjuryConfig)
    manager: ManagerConfig = Field(default_factory=ManagerConfig)


def config_hash(config: SimConfig) -> str:
    """Return a short stable hash of the full configuration (recorded on every match)."""
    text = canonical_json(config.model_dump(mode="json"))
    return hashlib.sha256(text.encode()).hexdigest()[:CONFIG_HASH_LENGTH]


def merge_config(base: SimConfig, overrides: Mapping[str, object]) -> SimConfig:
    """Return `base` with a partial, possibly nested, mapping of overrides applied and validated."""
    merged = _deep_merge(base.model_dump(mode="python"), overrides)
    return SimConfig.model_validate(merged)


def _deep_merge(base: Mapping[str, object], overrides: Mapping[str, object]) -> dict[str, object]:
    result = dict(base)
    for key, value in overrides.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = value
    return result
