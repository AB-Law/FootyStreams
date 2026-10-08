"""Home advantage through the crowd: a lift for the home side, pressure on the away side's nerves.

`crowd = fill x mean(atmosphere, proximity, passion) x 2 x crowd weight`, clamped to [0, 1]
(an empty ground has no crowd; a neutral venue has attendance 0). The home side's mental
attributes gain up to 12% x crowd, scaled by each player's `big_match`; the away side's composure
loses up to 7% x crowd x (0.5 + 0.5 toxicity). Everything is multiplied by
`SimConfig.home_advantage_scale`, the calibration lever (docs/design/02 section 8).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from footystreams.domain.match import MatchSetup
from footystreams.sim.config_world import HomeAdvantageConfig
from footystreams.sim.effective import MENTAL_FIELDS, Skills
from footystreams.sim.mathx import clamp
from footystreams.sim.side import Side

_PERCENT = 100.0


def crowd_level(setup: MatchSetup, cfg: HomeAdvantageConfig) -> float:
    """Return how big and loud the home crowd is in [0, 1]."""
    stadium, fans = setup.home.stadium, setup.home.fanbase
    capacity = stadium.capacity if stadium is not None else cfg.default_capacity
    fill = clamp(setup.attendance / capacity, 0.0, 1.0)
    atmosphere = stadium.atmosphere if stadium is not None else cfg.default_axis
    proximity = stadium.proximity if stadium is not None else cfg.default_axis
    passion = fans.passion if fans is not None else cfg.default_axis
    weight = stadium.home_advantage.crowd_weight if stadium is not None else cfg.default_axis
    return clamp(fill * (atmosphere + proximity + passion) / 3.0 * 2.0 * weight, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class Crowd:
    """The home crowd: how big and loud it is, and how hostile to visitors (both 0-1)."""

    level: float
    toxicity: float


NO_CROWD = Crowd(0.0, 0.0)


def crowd_of(setup: MatchSetup, cfg: HomeAdvantageConfig) -> Crowd:
    """Return the match's crowd (none when home advantage is switched off)."""
    if not cfg.enabled:
        return NO_CROWD
    fans = setup.home.fanbase
    toxicity = fans.toxicity if fans is not None else cfg.default_axis
    return Crowd(crowd_level(setup, cfg), toxicity)


def apply_crowd(
    skills: Skills, side: Side, crowd: Crowd, cfg: HomeAdvantageConfig, scale: float
) -> Skills:
    """Return the skills after the crowd: a mental lift at home, a composure dip away."""
    if crowd.level <= 0.0 or scale <= 0.0:
        return skills
    if side == "home":
        keen = cfg.big_match_share + (1.0 - cfg.big_match_share) * skills.big_match / _PERCENT
        lift = 1.0 + cfg.crowd_lift * crowd.level * scale * keen
        return replace(skills, **{name: getattr(skills, name) * lift for name in MENTAL_FIELDS})
    hostile = cfg.toxicity_share + (1.0 - cfg.toxicity_share) * crowd.toxicity
    return replace(
        skills,
        composure=skills.composure * (1.0 - cfg.away_pressure * crowd.level * scale * hostile),
    )
