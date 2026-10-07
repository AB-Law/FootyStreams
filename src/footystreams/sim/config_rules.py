"""Laws-of-the-game knobs: the referee and discipline (fouls, advantage, restarts)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag


class RefereeConfig(DomainModel):
    """How a referee turns a contact into a called foul (docs/design/02 section 6)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "threshold_base": "S",
        "strictness_swing": "S",
        "call_scale": "S",
        "consistency_noise": "S",
        "home_bias_scale": "S",
        "crowd_capacity": "S",
    }

    threshold_base: float = 0.55  # severity at which an average referee calls half of the contacts
    strictness_swing: float = 0.25  # a strict referee lowers the threshold by this much
    call_scale: float = 0.12  # width of the call probability's S-curve
    consistency_noise: float = 0.10  # threshold jitter of a fully inconsistent referee
    home_bias_scale: float = 0.15  # threshold shift per unit of home bias x crowd
    crowd_capacity: int = Field(ge=1, default=40_000)  # attendance that counts as a full crowd


class DisciplineConfig(DomainModel):
    """Fouls, advantage and the restart delays after them (docs/design/02 section 6)."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "contact_base": "S",
        "aggression_weight": "S",
        "dirtiness_weight": "S",
        "tackling_weight": "S",
        "derby_factor": "S",
        "severity_base": "S",
        "severity_spread": "S",
        "severity_aggression": "S",
        "severity_dirtiness": "S",
        "careless_max": "S",
        "reckless_max": "S",
        "advantage_scale": "S",
        "dogso_min_frame_x": "S",
        "dogso_max_defenders_ahead": "S",
        "free_kick_s": "S",
        "free_kick_spread_s": "S",
        "yellow_base": "S",
        "yellow_tendency_swing": "S",
        "yellow_strictness_swing": "S",
        "red_threshold": "S",
        "dogso_red_share": "S",
        "card_s": "S",
        "card_spread_s": "S",
        "min_players": "S",
    }

    # Chance a challenge involves foul-worthy contact, for an average man. 0 switches fouls off;
    # the default is raised to its calibrated value in the commit that enables M5 behaviour.
    contact_base: float = 0.0
    aggression_weight: float = 0.8
    dirtiness_weight: float = 0.5
    tackling_weight: float = 0.5  # better tacklers foul less
    derby_factor: float = 1.2
    severity_base: float = 0.25
    severity_spread: float = 0.5
    severity_aggression: float = 0.25
    severity_dirtiness: float = 0.20
    careless_max: float = 0.45
    reckless_max: float = 0.78
    advantage_scale: float = 0.5  # advantage chance = scale x the referee's advantage tendency
    dogso_min_frame_x: float = 0.70  # fouled man must be this far up the pitch to be "through"
    dogso_max_defenders_ahead: int = 1  # defenders (keeper included) between him and the goal
    free_kick_s: float = 25.0
    free_kick_spread_s: float = 10.0
    yellow_base: float = 0.68  # severity above which an average referee books a foul
    yellow_tendency_swing: float = 0.20  # a card-happy referee books milder fouls
    yellow_strictness_swing: float = 0.10
    red_threshold: float = 0.90  # severity above which a foul is a straight red
    dogso_red_share: float = 0.60  # share of denied goal-scoring chances punished with a red
    card_s: float = 30.0
    card_spread_s: float = 10.0
    min_players: int = Field(ge=1, le=11, default=7)  # a side is never reduced below this
