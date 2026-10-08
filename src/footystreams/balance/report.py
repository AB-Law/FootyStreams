"""Plain-text tables for ``uv run balance``: the targets table and the loss line."""

from __future__ import annotations

import math
from collections.abc import Sequence

from footystreams.balance.evaluate import MetricResult, Verdict, failures, total_loss

NAME_WIDTH = 32


def _number(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.3f}".rstrip("0").rstrip(".")


def format_row(result: MetricResult) -> str:
    """One line: name, value, 95% interval, band and verdict."""
    interval = f"[{_number(result.low)}, {_number(result.high)}]"
    band = f"{_number(result.target.min)} - {_number(result.target.max)}"
    return (
        f"{result.name:<{NAME_WIDTH}} {_number(result.value):>9} {interval:>20} "
        f"{_number(result.target.target):>8} {band:>14}  {result.verdict.value}"
    )


def format_report(results: Sequence[MetricResult], matches: int, profile: str) -> str:
    """The full targets table with a summary line."""
    header = (
        f"{'metric':<{NAME_WIDTH}} {'value':>9} {'95% interval':>20} "
        f"{'target':>8} {'band':>14}  verdict"
    )
    passed = sum(r.verdict is Verdict.PASS for r in results)
    lines = [f"profile {profile}, {matches} matches", header, "-" * len(header)]
    lines += [format_row(result) for result in results]
    lines.append("-" * len(header))
    lines.append(f"{passed}/{len(results)} PASS, loss {total_loss(results):.3f}")
    return "\n".join(lines)


def format_failures(results: Sequence[MetricResult]) -> str:
    """Only the metrics that miss, worst first (by loss)."""
    worst = sorted(failures(results), key=lambda r: r.loss, reverse=True)
    return "\n".join(format_row(result) for result in worst)
