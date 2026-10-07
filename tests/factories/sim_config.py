"""Simulation configs for tests: the shipped defaults and a card-heavy variant."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from footystreams.sim import SimConfig, merge_config

# M5 behaviour is on by default; the name stays so tests say what they rely on.
M5_OVERRIDES: Mapping[str, Any] = {}

# A config that produces cards, penalties and dismissals within a handful of matches.
CARD_HEAVY: Mapping[str, Any] = {
    "discipline": {"contact_base": 3.0, "yellow_base": 0.3, "red_threshold": 0.75},
}


def m5_config(extra: Mapping[str, Any] | None = None) -> SimConfig:
    """Return the config with all M5 behaviour on, plus optional overrides."""
    config = merge_config(SimConfig(), M5_OVERRIDES)
    return merge_config(config, extra) if extra else config
