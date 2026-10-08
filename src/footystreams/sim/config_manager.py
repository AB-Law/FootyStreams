"""Manager knobs: substitution rules and the AI manager (docs/design/02 section 11)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag


class ManagerConfig(DomainModel):
    """Substitution rules and the AI manager that makes the changes (02 section 11)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "enabled": "S",
        "max_subs": "S",
        "max_windows": "S",
        "window_gap_s": "S",
        "sub_s": "S",
        "sub_spread_s": "S",
        "review_base_s": "S",
        "review_slow": "S",
        "review_flexibility": "S",
        "review_jitter": "S",
        "noise_scale": "S",
        "stay_weight": "S",
        "fatigue_threshold": "S",
        "fatigue_gain": "S",
        "min_fit": "S",
        "chase_from_min": "S",
        "protect_from_min": "S",
        "shift_cooldown_s": "S",
        "tactical_gain": "S",
        "card_gain": "S",
        "yellow_from_min": "S",
        "yellow_until_min": "S",
        "yellow_aggression": "S",
        "yellow_gain": "S",
    }

    enabled: bool = True  # the AI manager; forced injury changes happen regardless
    max_subs: int = Field(ge=0, le=11, default=5)
    max_windows: int = Field(ge=0, le=11, default=3)  # stoppages in which changes may be made
    window_gap_s: float = 20.0  # changes closer together than this share one window
    sub_s: float = 30.0  # stoppage per substitution
    sub_spread_s: float = 8.0
    review_base_s: float = 300.0  # checkpoint spacing: base x (slow - flexibility x flex) +- jitter
    review_slow: float = 1.4
    review_flexibility: float = 0.8
    review_jitter: float = 0.25
    noise_scale: float = 0.30  # sd of the apparent exhaustion of a manager with no tactical sense
    stay_weight: float = 0.6  # the prior for doing nothing at a checkpoint
    fatigue_threshold: float = 0.25  # apparent exhaustion above which a fresh-legs change appeals
    fatigue_gain: float = 8.0
    min_fit: int = Field(ge=0, le=100, default=30)  # least competence a replacement needs
    chase_from_min: float = 60.0
    protect_from_min: float = 70.0
    shift_cooldown_s: float = 480.0  # a manager lets a change of mentality settle
    tactical_gain: float = 2.0  # appeal of chasing or protecting per goal of margin (up to 2)
    card_gain: float = 2.0  # appeal of reshaping after a dismissal
    yellow_from_min: float = 25.0
    yellow_until_min: float = 70.0
    yellow_aggression: float = 60.0  # booked players at least this aggressive are a risk
    yellow_gain: float = 1.5
