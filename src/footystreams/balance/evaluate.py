"""Score a set of samples against a profile: value, 95% interval, verdict and a weighted loss.

The interval comes from batch means: the samples are dealt into a fixed number of interleaved
batches, the metric is computed on each, and the spread of those values gives a Student-t interval.
That works for any metric (ratios, rates, spreads) without a formula per metric, and it is
deterministic because the batches are a function of sample order.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean, stdev

from footystreams.balance.metrics import METRICS
from footystreams.balance.sample import MatchSample
from footystreams.balance.targets import Target

BATCHES = 10
T_95 = 2.262  # Student-t, two-sided 95%, BATCHES - 1 = 9 degrees of freedom
MAX_LOSS = 100.0  # per unit of weight; an undefined metric scores this, never better than a miss


class Verdict(StrEnum):
    """Where a metric sits relative to its band."""

    PASS = "PASS"  # noqa: S105 - a verdict, not a credential
    LOW = "LOW"
    HIGH = "HIGH"
    UNDEFINED = "n/a"


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One metric measured against its target."""

    name: str
    value: float
    low: float
    high: float
    target: Target
    verdict: Verdict

    @property
    def loss(self) -> float:
        """Weighted squared miss, in band half-widths."""
        if math.isnan(self.value):
            return self.target.weight * MAX_LOSS
        miss = (self.value - self.target.target) / self.target.half_width
        return self.target.weight * min(miss * miss, MAX_LOSS)


def _interval(name: str, samples: Sequence[MatchSample], value: float) -> tuple[float, float]:
    """The 95% interval of metric ``name``; it is the value itself with too few samples."""
    if len(samples) < BATCHES * 2:
        return value, value
    values = [METRICS[name](samples[start::BATCHES]) for start in range(BATCHES)]
    if any(math.isnan(v) for v in values):
        return math.nan, math.nan
    half = T_95 * stdev(values) / math.sqrt(BATCHES)
    return value - half, value + half


def _verdict(value: float, target: Target) -> Verdict:
    if math.isnan(value):
        return Verdict.UNDEFINED
    if value < target.min:
        return Verdict.LOW
    return Verdict.HIGH if value > target.max else Verdict.PASS


def evaluate(samples: Sequence[MatchSample], targets: Mapping[str, Target]) -> list[MetricResult]:
    """Measure every targeted metric on ``samples``; results follow the order of ``targets``."""
    results = []
    for name, target in targets.items():
        value = METRICS[name](samples)
        low, high = _interval(name, samples, value)
        results.append(MetricResult(name, value, low, high, target, _verdict(value, target)))
    return results


def total_loss(results: Sequence[MetricResult]) -> float:
    """The weighted loss summed over metrics: what the fit minimises."""
    return fmean(r.loss for r in results) if results else 0.0


def failures(results: Sequence[MetricResult]) -> list[MetricResult]:
    """The metrics outside their band (or undefined)."""
    return [r for r in results if r.verdict is not Verdict.PASS]
