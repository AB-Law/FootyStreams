"""The shipped balance against the `realistic` profile (docs/design/02 section 14).

Two tiers: 200 matches against bands widened by `FAST_BAND_FACTOR` guard against drift in every
pull request; the full 1,200 matches against the real bands run nightly and before a milestone
closes. Both play every ordered pairing of the committed default world and read the targets from
`data/static/balance_targets.yaml`, so retuning the league means editing that file, not these tests.
"""

from __future__ import annotations

import pytest

from footystreams.balance.evaluate import MetricResult, evaluate, failures
from footystreams.balance.report import format_failures
from footystreams.balance.targets import FAST_BAND_FACTOR, Tier
from footystreams.cli.balance import build_parser
from footystreams.cli.balance_session import Session, open_session

FAST_MATCHES = 200
FULL_MATCHES = 1200
WORKERS = 4

# Metrics the shipped defaults still miss at the end of M8 (docs/milestones/M8.md). The full run
# fails on any *other* miss, so a regression is caught; remove a name here when its gap is fixed.
KNOWN_GAPS = frozenset(
    {
        "second_half_goal_share_pct",  # goals thin out at 60-75 min: needs late-game dynamics
        "late_goal_share_pct",  # same cause
        "possession_spread_pp",
        "corners_per_match",
        "on_target_per_shot",  # on the band edge
        "reds_per_match",  # on the band edge
        "penalty_conversion_pct",  # on the band edge
        "underdog_win_pct_even",  # 56 pairings: the even bin is a handful of them
        "draw_pct_small",
        "home_favourite_edge_pp",
    }
)


def _session(matches: int) -> Session:
    return open_session(
        build_parser().parse_args(["--matches", str(matches), "--workers", str(WORKERS)])
    )


def _message(results: list[MetricResult]) -> str:
    return "metrics outside their band:\n" + format_failures(results)


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(600)
def test_balance__the_fast_tier_metrics_sit_inside_widened_bands() -> None:
    session = _session(FAST_MATCHES)
    targets = {
        name: target.widened(FAST_BAND_FACTOR)
        for name, target in session.profile.tier(Tier.FAST).items()
    }
    with session.runner() as runner:
        results = evaluate(runner.run(session.config), targets)

    assert not failures(results), _message(results)


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(1800)
def test_balance__no_metric_outside_its_band_over_the_full_run_is_a_new_miss() -> None:
    session = _session(FULL_MATCHES)
    with session.runner() as runner:
        results = evaluate(runner.run(session.config), session.profile.metrics)

    new = [r for r in failures(results) if r.name not in KNOWN_GAPS]
    assert not new, _message(new)
