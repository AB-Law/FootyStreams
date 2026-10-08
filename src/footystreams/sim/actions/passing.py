"""Pass classification and success probability (docs/design/02 section 5.3)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from footystreams.sim.config import PassConfig
from footystreams.sim.effective import Skills
from footystreams.sim.geometry import CENTRE, Point
from footystreams.sim.mathx import PERCENT, clamp, squash

_BACKWARD = -0.02  # frame-x change below which a pass counts as a back pass


class PassKind(StrEnum):
    """The kind of pass; it changes the base success rate, the skill used and the duration."""

    SHORT = "short"
    LONG = "long"
    THROUGH = "through"
    CROSS = "cross"
    BACK = "back"


def classify_pass(carrier: Point, mate: Point, length_m: float, cfg: PassConfig) -> PassKind:
    """Name a pass from the frame positions of passer and target and its length."""
    gain = mate[0] - carrier[0]
    if gain < _BACKWARD:
        return PassKind.BACK
    wide_target = abs(mate[1] - CENTRE) > cfg.cross_wide_offset
    wide_carrier = abs(carrier[1] - CENTRE) > cfg.cross_wide_offset
    if carrier[0] >= cfg.cross_min_frame_x and wide_carrier and not wide_target:
        return PassKind.CROSS
    if length_m > cfg.long_pass_m:
        return PassKind.LONG
    if gain >= cfg.through_min_gain and length_m >= cfg.through_min_length_m:
        return PassKind.THROUGH
    return PassKind.SHORT


def pass_skill(kind: PassKind, passer: Skills) -> float:
    """Return the skill (1-100 scale) that decides how well this pass is executed."""
    if kind is PassKind.LONG:
        return passer.long_passing
    if kind is PassKind.CROSS:
        return passer.crossing
    if kind is PassKind.THROUGH:
        return 0.5 * passer.vision + 0.5 * passer.short_passing
    return passer.short_passing


def _base(kind: PassKind, cfg: PassConfig) -> float:
    return {
        PassKind.SHORT: cfg.base_short,
        PassKind.LONG: cfg.base_long,
        PassKind.THROUGH: cfg.base_through,
        PassKind.CROSS: cfg.base_cross,
        PassKind.BACK: cfg.base_back,
    }[kind]


_WEATHER_SENSITIVE = (PassKind.LONG, PassKind.CROSS, PassKind.THROUGH)


@dataclass(frozen=True, slots=True)
class PassAttempt:
    """Everything the success model needs to know about one pass."""

    kind: PassKind
    length_m: float
    skill: float  # passer's skill for this kind, 1-100
    receiver_touch: float  # receiver's first touch, 1-100
    pressure: float  # pressure on the passer, 0-1
    openness: float  # how free the receiver is, 0-1
    environment: float = 0.0  # success lost to weather and pitch (long balls only)


def difficulty_of(length_m: float, cfg: PassConfig) -> float:
    """Return how much pressure and a marked receiver matter at this length: more on a long ball."""
    share = min(length_m / cfg.difficulty_span_m, 1.0)
    return cfg.difficulty_floor + (cfg.difficulty_peak - cfg.difficulty_floor) * share


def pass_success_probability(attempt: PassAttempt, cfg: PassConfig) -> float:
    """Return the chance the pass reaches its target.

    Starts from the kind's base, subtracts a per-metre penalty, adds the passer's skill above or
    below average and the receiver's first touch, then subtracts pressure on the passer and the
    receiver's lack of openness.
    """
    skill_term = cfg.skill_swing * (
        squash((attempt.skill - cfg.skill_pivot) / cfg.skill_scale) - 0.5
    )
    touch_term = cfg.receiver_touch_weight * (attempt.receiver_touch - cfg.skill_pivot) / PERCENT
    probability = (
        _base(attempt.kind, cfg)
        - cfg.length_penalty_per_m * max(0.0, attempt.length_m - cfg.length_free_m)
        + skill_term
        + touch_term
        - difficulty_of(attempt.length_m, cfg)
        * (
            cfg.pressure_penalty * attempt.pressure**cfg.pressure_exponent
            + cfg.openness_penalty * (1.0 - attempt.openness) ** cfg.openness_exponent
        )
        - (attempt.environment if attempt.kind in _WEATHER_SENSITIVE else 0.0)
    )
    return clamp(probability, cfg.min_probability, cfg.max_probability)
