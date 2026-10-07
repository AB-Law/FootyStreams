"""Event context and enrichment: what the simulator records beside what happened."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from footystreams.domain.base import DomainModel, UsageTag


class ContextConfig(DomainModel):
    """Causal context (momentum, intensity, tags) and enriched pass, dribble and shot fields."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "progressive_frame_x": "S",
        "big_chance_xg": "S",
    }

    enabled: bool = False  # switched on in the commit that enables M7 behaviour
    progressive_frame_x: float = 0.25  # a pass is progressive when it gains this much pitch
    big_chance_xg: float = 0.30
