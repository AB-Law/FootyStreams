"""Event context and enrichment: what the simulator records beside what happened."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag


class ContextConfig(DomainModel):
    """Causal context (momentum, intensity, tags) and enriched pass, dribble and shot fields."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "progressive_frame_x": "S",
        "big_chance_xg": "S",
    }

    enabled: bool = True
    # a pass is progressive when it gains this much pitch
    progressive_frame_x: float = Field(gt=0.0, le=1.0, default=0.25)
    big_chance_xg: float = Field(gt=0.0, le=1.0, default=0.30)
