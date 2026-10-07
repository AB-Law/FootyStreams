"""SimConfig: every tunable of the simulation, frozen, hashable and mergeable.

One group per concern (docs/design/02 section 14.6); groups are added by the milestone that
introduces the behaviour. `config_hash` identifies the exact numbers a match was played with.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.canonical import canonical_json

CONFIG_HASH_LENGTH = 16


class SimConfig(DomainModel):
    """Top-level simulation configuration (defaults are the shipped balance)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "model_profile": "S",
        "emit_frames": "S",
        "frame_interval_s": "S",
        "home_advantage_scale": "S",
    }

    model_profile: str = "v1"
    emit_frames: bool = False
    frame_interval_s: int = Field(ge=1, le=60, default=1)
    home_advantage_scale: float = Field(ge=0.0, le=3.0, default=1.0)


def config_hash(config: SimConfig) -> str:
    """Return a short stable hash of the full configuration (recorded on every match)."""
    text = canonical_json(config.model_dump(mode="json"))
    return hashlib.sha256(text.encode()).hexdigest()[:CONFIG_HASH_LENGTH]


def merge_config(base: SimConfig, overrides: Mapping[str, Any]) -> SimConfig:
    """Return `base` with a partial, possibly nested, mapping of overrides applied and validated."""
    merged = _deep_merge(base.model_dump(mode="python"), overrides)
    return SimConfig.model_validate(merged)


def _deep_merge(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overrides.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = value
    return result
