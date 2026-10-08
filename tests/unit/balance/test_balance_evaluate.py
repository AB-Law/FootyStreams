from __future__ import annotations

import math

from footystreams.balance.evaluate import MAX_LOSS, Verdict, evaluate, failures, total_loss
from footystreams.balance.report import format_failures, format_report
from footystreams.balance.sample import MatchSample
from footystreams.balance.targets import Target
from tests.factories.balance import make_sample, make_side

GOALS = Target(target=2.0, min=1.0, max=3.0, weight=2.0)


def _goals(count: int) -> list[MatchSample]:
    return [make_sample(make_side(goals=count), make_side(goals=0))] * 40


def test_evaluate__a_value_inside_the_band_passes_with_no_loss_at_the_target() -> None:
    (result,) = evaluate(_goals(2), {"goals_per_match": GOALS})

    assert result.verdict is Verdict.PASS
    assert result.loss == 0.0


def test_evaluate__outside_the_band_is_low_or_high() -> None:
    (low,) = evaluate(_goals(0), {"goals_per_match": GOALS})
    (high,) = evaluate(_goals(5), {"goals_per_match": GOALS})

    assert (low.verdict, high.verdict) == (Verdict.LOW, Verdict.HIGH)


def test_evaluate__an_undefined_metric_is_n_a_and_costs_the_maximum() -> None:
    target = Target(target=77, min=74, max=80)

    (result,) = evaluate([make_sample()] * 40, {"penalty_conversion_pct": target})

    assert result.verdict is Verdict.UNDEFINED
    assert result.loss == MAX_LOSS


def test_loss__is_weighted_squared_misses_in_band_half_widths_and_capped() -> None:
    (near,) = evaluate(_goals(3), {"goals_per_match": GOALS})
    (far,) = evaluate(_goals(900), {"goals_per_match": GOALS})

    assert near.loss == 2.0
    assert far.loss == 2.0 * MAX_LOSS


def test_interval__brackets_the_value_and_collapses_for_few_samples() -> None:
    varied = [make_sample(make_side(goals=g % 4), make_side(goals=0)) for g in range(100)]
    (wide,) = evaluate(varied, {"goals_per_match": GOALS})
    (few,) = evaluate(varied[:5], {"goals_per_match": GOALS})

    assert wide.low <= wide.value <= wide.high
    assert few.low == few.value == few.high


def test_total_loss_and_failures__summarise_the_results() -> None:
    results = evaluate(_goals(5), {"goals_per_match": GOALS})

    assert total_loss(results) == results[0].loss
    assert failures(results) == results
    assert total_loss([]) == 0.0
    assert math.isfinite(total_loss(results))


def test_report__lists_each_metric_with_its_verdict_and_a_summary() -> None:
    results = evaluate(_goals(2), {"goals_per_match": GOALS})

    text = format_report(results, 40, "realistic")

    assert "profile realistic, 40 matches" in text
    assert "goals_per_match" in text
    assert "1/1 PASS" in text


def test_report__failures_come_worst_first() -> None:
    targets = {
        "shots_per_team": Target(target=20, min=19, max=21),  # 12 shots: loss 64
        "goals_per_match": GOALS,  # 9 goals: loss 98
    }

    lines = format_failures(evaluate(_goals(9), targets)).splitlines()

    assert [line.split()[0] for line in lines] == ["goals_per_match", "shots_per_team"]
