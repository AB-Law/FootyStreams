"""Simulation configs for tests: all dead-ball and discipline behaviour switched on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from footystreams.sim import SimConfig, merge_config

# Everything M5 adds, switched on with calibrated-ish values. After the commit that enables M5 by
# default these equal the defaults and the factory simply returns SimConfig().
M5_OVERRIDES: Mapping[str, Any] = {
    "discipline": {"contact_base": 0.45},
    "restarts": {
        "enabled": True,
        "clearance_out_share": 0.5,
        "blocked_corner_share": 0.5,
        "parry_corner_share": 0.5,
        "cross_corner_share": 0.5,
        "overhit_min_m": 6.0,
        "overhit_max_m": 20.0,
    },
    "challenge": {"fail_intercept": 0.42, "fail_loose": 0.18},
    "offside": {"enabled": True},
    "stoppage": {"enabled": True},
}

# A config that produces cards, penalties and dismissals within a handful of matches.
CARD_HEAVY: Mapping[str, Any] = {
    "discipline": {"contact_base": 3.0, "yellow_base": 0.3, "red_threshold": 0.75},
}


def m5_config(extra: Mapping[str, Any] | None = None) -> SimConfig:
    """Return the config with all M5 behaviour on, plus optional overrides."""
    config = merge_config(SimConfig(), M5_OVERRIDES)
    return merge_config(config, extra) if extra else config
