"""Balance targets and profiles, read from ``data/static/balance_targets.yaml``.

A ``Target`` is a number with an acceptable band; a ``Profile`` is the set of targets for one kind
of league. A profile may ``extends`` another and replace some of its metrics, so ``chaos`` need only
say what is different. Unknown metric names are rejected so a typo cannot silently go unchecked.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from footystreams.balance.metrics import METRICS
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model

TARGETS_FILE = "balance_targets.yaml"
DEFAULT_PROFILE = "realistic"
FAST_BAND_FACTOR = 2.0  # the fast tier runs few matches, so it accepts bands this much wider


class Tier(StrEnum):
    """Which test run asserts a metric."""

    FAST = "fast"
    SLOW = "slow"


class Target(YamlModel):
    """One metric's target, acceptable band, loss weight and tier."""

    target: float
    min: float
    max: float
    weight: float = Field(gt=0.0, default=1.0)
    tier: Tier = Tier.SLOW

    @model_validator(mode="after")
    def _target_sits_inside_the_band(self) -> Self:
        if not self.min <= self.target <= self.max:
            msg = f"target {self.target} is outside its band [{self.min}, {self.max}]"
            raise ValueError(msg)
        return self

    @property
    def half_width(self) -> float:
        """Half the band: the scale on which a miss is measured (never zero)."""
        return max((self.max - self.min) / 2.0, 1e-9)

    def widened(self, factor: float) -> Target:
        """The same target with its band scaled about the target (for the fast tier)."""
        return self.model_copy(
            update={
                "min": self.target - (self.target - self.min) * factor,
                "max": self.target + (self.max - self.target) * factor,
            }
        )


class _RawProfile(YamlModel):
    description: str
    extends: str | None = None
    metrics: dict[str, Target]


class _RawFile(YamlModel):
    profiles: dict[str, _RawProfile]


class Profile(YamlModel):
    """A named set of targets, with ``extends`` already applied."""

    name: str
    description: str
    metrics: Mapping[str, Target]

    def tier(self, tier: Tier) -> dict[str, Target]:
        """The targets asserted at ``tier`` (the fast tier is a subset of the slow run)."""
        return {name: t for name, t in self.metrics.items() if tier is Tier.SLOW or t.tier is tier}


def _resolve(name: str, raw: _RawFile) -> Profile:
    profile = raw.profiles[name]
    metrics: dict[str, Target] = {}
    if profile.extends is not None:
        parent = raw.profiles.get(profile.extends)
        if parent is None or parent.extends is not None:
            msg = (
                f"{TARGETS_FILE}: profile {name!r} extends {profile.extends!r}, "
                "which must be a base profile"
            )
            raise StaticDataError(msg)
        metrics.update(parent.metrics)
    metrics.update(profile.metrics)
    unknown = sorted(set(metrics) - set(METRICS))
    if unknown:
        msg = f"{TARGETS_FILE}: profile {name!r} has unknown metrics {unknown}"
        raise StaticDataError(msg)
    return Profile(name=name, description=profile.description, metrics=metrics)


def load_profiles(directory: Path | None = None) -> dict[str, Profile]:
    """Every profile in the targets file, by name."""
    raw = load_model(_RawFile, TARGETS_FILE, directory)
    return {name: _resolve(name, raw) for name in raw.profiles}


def load_profile(name: str = DEFAULT_PROFILE, directory: Path | None = None) -> Profile:
    """The profile called ``name``; the error lists the profiles that exist."""
    profiles = load_profiles(directory)
    if name not in profiles:
        msg = f"unknown balance profile {name!r}; choose one of {sorted(profiles)}"
        raise StaticDataError(msg)
    return profiles[name]
