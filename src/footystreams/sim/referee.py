"""The referee as the simulation sees him: a few unit-range tendencies and the call model.

A contact becomes a called foul with probability `squash((severity - threshold) / scale)`, where a
stricter referee has a lower threshold, an inconsistent one a jittery threshold, and the home
crowd tilts the threshold against the away side in proportion to the referee's `home_bias`
(docs/design/02 sections 6 and 8). The sim receives a `Referee` model optionally; without one a
neutral referee officiates.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.referee import Referee
from footystreams.sim.config import RefereeConfig
from footystreams.sim.mathx import clamp, squash
from footystreams.sim.rng import SimRng
from footystreams.sim.side import Side


@dataclass(frozen=True, slots=True)
class RefereeProfile:
    """Decision tendencies of the match referee (all unit range except `home_bias`)."""

    strictness: float
    consistency: float
    home_bias: float  # signed: negative means an overcompensating referee
    card_tendency: float
    advantage_tendency: float
    added_time_generosity: float
    penalty_propensity: float


NEUTRAL_REFEREE = RefereeProfile(0.5, 0.5, 0.0, 0.5, 0.5, 0.5, 0.5)


def referee_profile(referee: Referee | None) -> RefereeProfile:
    """Return the profile of a `Referee` model, or the neutral referee when there is none."""
    if referee is None:
        return NEUTRAL_REFEREE
    return RefereeProfile(
        strictness=referee.strictness,
        consistency=referee.consistency,
        home_bias=referee.home_bias,
        card_tendency=referee.card_tendency,
        advantage_tendency=referee.advantage_tendency,
        added_time_generosity=referee.added_time_generosity,
        penalty_propensity=referee.penalty_propensity,
    )


def crowd_pressure(attendance: int, cfg: RefereeConfig) -> float:
    """Return how full the ground is in [0, 1], the share of the crowd a referee feels."""
    return clamp(attendance / cfg.crowd_capacity, 0.0, 1.0)


def call_threshold(profile: RefereeProfile, tilt: float, noise: float, cfg: RefereeConfig) -> float:
    """Return the severity above which this referee calls a contact.

    `threshold_base - strictness_swing x strictness`, lowered by the crowd `tilt` and jittered by
    `noise`, a standard-normal draw scaled by how inconsistent the referee is.
    """
    base = cfg.threshold_base - cfg.strictness_swing * profile.strictness
    jitter = cfg.consistency_noise * (1.0 - profile.consistency) * noise
    return base - tilt + jitter


def home_tilt(
    profile: RefereeProfile, fouling_side: Side, crowd: float, cfg: RefereeConfig
) -> float:
    """Return the threshold shift caused by the crowd.

    A home-biased referee under a loud crowd calls away fouls more readily (negative shift lowers
    the threshold) and home fouls less readily; a negative `home_bias` reverses it.
    """
    shift = cfg.home_bias_scale * profile.home_bias * crowd
    return shift if fouling_side == "away" else -shift


def call_probability(severity: float, threshold: float, cfg: RefereeConfig) -> float:
    """Return the chance a contact of this severity is called, given the threshold."""
    return squash((severity - threshold) / cfg.call_scale)


def is_called(
    profile: RefereeProfile, severity: float, tilt: float, cfg: RefereeConfig, rng: SimRng
) -> bool:
    """Decide whether the referee calls a contact (consumes a noise draw and one more)."""
    threshold = call_threshold(profile, tilt, rng.gauss(), cfg)
    return rng.u() < call_probability(severity, threshold, cfg)
