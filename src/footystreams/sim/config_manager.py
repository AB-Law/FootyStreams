"""Manager knobs: substitution rules and the AI manager (docs/design/02 section 11)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag


class ManagerConfig(DomainModel):
    """Substitution rules (from MatchRules in the design) and substitution timing."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "max_subs": "S",
        "max_windows": "S",
        "window_gap_s": "S",
        "sub_s": "S",
        "sub_spread_s": "S",
    }

    enabled: bool = False  # switched on in the commit that enables M6 behaviour
    max_subs: int = Field(ge=0, le=11, default=5)
    max_windows: int = Field(ge=0, le=11, default=3)  # stoppages in which changes may be made
    window_gap_s: float = 20.0  # changes closer together than this share one window
    sub_s: float = 30.0  # stoppage per substitution
    sub_spread_s: float = 8.0
