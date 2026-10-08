from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from footystreams.balance.metrics import METRICS
from footystreams.balance.targets import Target, Tier, load_profile, load_profiles
from footystreams.seed.static.files import StaticDataError

PROFILES = ("realistic", "high_scoring", "defensive_grind", "chaos")


def test_load_profiles__the_four_named_profiles_exist() -> None:
    assert sorted(load_profiles()) == sorted(PROFILES)


def test_realistic__targets_every_metric_the_harness_measures() -> None:
    assert sorted(load_profile("realistic").metrics) == sorted(METRICS)


@pytest.mark.parametrize("name", PROFILES)
def test_every_profile__has_the_full_metric_set_with_targets_inside_their_bands(name: str) -> None:
    profile = load_profile(name)

    assert sorted(profile.metrics) == sorted(METRICS)
    assert all(t.min <= t.target <= t.max for t in profile.metrics.values())


def test_extends__a_profile_replaces_only_the_metrics_it_lists() -> None:
    realistic, chaos = load_profile("realistic"), load_profile("chaos")

    assert chaos.metrics["reds_per_match"].target > realistic.metrics["reds_per_match"].target
    assert chaos.metrics["goals_per_match"] == realistic.metrics["goals_per_match"]


def test_tier__the_fast_tier_is_a_subset_of_the_slow_run() -> None:
    profile = load_profile("realistic")

    fast, slow = profile.tier(Tier.FAST), profile.tier(Tier.SLOW)

    assert 0 < len(fast) < len(slow) == len(profile.metrics)
    assert "goals_per_match" in fast


def test_unknown_profile__lists_the_ones_that_exist() -> None:
    with pytest.raises(StaticDataError, match="realistic"):
        load_profile("utopia")


def test_target__outside_its_band_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Target(target=5, min=1, max=2)


def test_widened__scales_the_band_about_the_target() -> None:
    wide = Target(target=10, min=8, max=11).widened(2.0)

    assert (wide.min, wide.max) == (6.0, 12.0)


def _write(directory: Path, text: str) -> None:
    (directory / "balance_targets.yaml").write_text(text, encoding="utf-8")


def test_a_typo_in_a_metric_name__is_rejected_naming_it(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "profiles:\n  p:\n    description: d\n    metrics:\n"
        "      goals_per_matchh: {target: 1, min: 0, max: 2}\n",
    )

    with pytest.raises(StaticDataError, match="goals_per_matchh"):
        load_profiles(tmp_path)


def test_extending_an_extending_profile__is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "profiles:\n  a:\n    description: d\n    metrics: {}\n"
        "  b:\n    description: d\n    extends: a\n    metrics: {}\n"
        "  c:\n    description: d\n    extends: b\n    metrics: {}\n",
    )

    with pytest.raises(StaticDataError, match="base profile"):
        load_profiles(tmp_path)
