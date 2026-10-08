"""Which knob moves which metric: nudge each knob up and down and see what changes.

Every knob is multiplied by ``1 - r`` and ``1 + r`` (r is 20% by default) and the same scenarios
are replayed. The effect on a metric is the change across that range measured in half-widths of the
metric's band, so effects of goals per match and of red cards compare on one scale. A knob whose
nudge is illegal (the validators refuse it) on one side uses the other side against the base and
doubles the difference; if both sides are illegal the knob is reported as unmoveable.

Matches diverge once any knob changes, so every effect carries the sampling noise of the run; the
base run's interval, in the same units, is shown next to the matrix so a reader can tell a real
effect from noise.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from footystreams.balance.evaluate import MetricResult
from footystreams.balance.knobs import Knob, with_multipliers
from footystreams.balance.metrics import METRICS
from footystreams.balance.sample import MatchSample
from footystreams.balance.targets import Target
from footystreams.sim.config import SimConfig

DEFAULT_RELATIVE_STEP = 0.2
NAME_WIDTH = 34
COLUMN_WIDTH = 9

Play = Callable[[SimConfig], Sequence[MatchSample]]


@dataclass(frozen=True, slots=True)
class Sensitivity:
    """The effect of one knob on each metric, in band half-widths; ``None`` when unmoveable."""

    knob: Knob
    effects: Mapping[str, float] | None


def _values(samples: Sequence[MatchSample], metrics: Sequence[str]) -> dict[str, float]:
    return {name: METRICS[name](samples) for name in metrics}


def _config_at(base: SimConfig, knob: Knob, multiplier: float) -> SimConfig | None:
    try:
        return with_multipliers(base, [knob], {knob.path: multiplier})
    except ValueError:
        return None


def _effects(
    low: Mapping[str, float] | None,
    high: Mapping[str, float] | None,
    base: Mapping[str, float],
    targets: Mapping[str, Target],
) -> dict[str, float] | None:
    if low is None and high is None:
        return None
    result = {}
    for name, target in targets.items():
        if low is not None and high is not None:
            change = high[name] - low[name]
        elif high is not None:
            change = 2.0 * (high[name] - base[name])
        else:
            assert low is not None  # noqa: S101 - narrowed above: not both None
            change = 2.0 * (base[name] - low[name])
        result[name] = change / target.half_width
    return result


class Sides(StrEnum):
    """Which nudges a sweep plays: down and up (a central difference) or only up (half the cost)."""

    BOTH = "both"
    UP = "up"


@dataclass(frozen=True, slots=True)
class Baseline:
    """The config being nudged and the metrics it produced on the scenarios."""

    config: SimConfig
    values: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class SweepOptions:
    """How a sweep runs: the nudge, its sides, knobs already done and a callback per new result."""

    relative: float = DEFAULT_RELATIVE_STEP
    sides: Sides = Sides.BOTH
    done: Mapping[str, Sensitivity] = field(default_factory=dict)
    record: Callable[[Sensitivity], None] | None = None


def _nudged(
    play: Play,
    base: SimConfig,
    knob: Knob,
    names: Sequence[str],
    options: SweepOptions,
) -> tuple[Mapping[str, float] | None, Mapping[str, float] | None]:
    """The metrics with the knob nudged (down, up); a side that is not played or illegal is None.

    Playing up only, a knob that cannot go up (already at its maximum) is nudged down instead.
    """

    def side(multiplier: float) -> Mapping[str, float] | None:
        config = _config_at(base, knob, multiplier)
        return None if config is None else _values(play(config), names)

    up = side(1.0 + options.relative)
    if options.sides is Sides.BOTH:
        return side(1.0 - options.relative), up
    return (side(1.0 - options.relative) if up is None else None), up


def sweep(
    play: Play,
    baseline: Baseline,
    knobs: Sequence[Knob],
    targets: Mapping[str, Target],
    options: SweepOptions | None = None,
) -> list[Sensitivity]:
    """Replay the scenarios with each knob nudged away from ``baseline``.

    Knobs in ``options.done`` are not replayed (a resumed run); each new result goes to
    ``options.record`` the moment it exists, so an interrupted run loses at most one knob.
    """
    chosen = options or SweepOptions()
    names = list(targets)
    results = []
    for knob in knobs:
        known = chosen.done.get(knob.path)
        if known is not None:
            results.append(known)
            continue
        low, high = _nudged(play, baseline.config, knob, names, chosen)
        found = Sensitivity(knob, _effects(low, high, baseline.values, targets))
        if chosen.record is not None:
            chosen.record(found)
        results.append(found)
    return results


def noise_floor(results: Sequence[MetricResult]) -> dict[str, float]:
    """Each metric's base-run 95% interval half-width, in band half-widths (the noise to beat)."""
    return {
        r.name: (r.high - r.low) / 2.0 / r.target.half_width
        for r in results
        if not math.isnan(r.low) and not math.isnan(r.high)
    }


def _cell(effect: float, noise: float) -> str:
    mark = "*" if abs(effect) > noise else " "
    return f"{effect:+.2f}{mark}".rjust(COLUMN_WIDTH)


def format_matrix(
    sensitivities: Sequence[Sensitivity], metrics: Sequence[str], noise: Mapping[str, float]
) -> str:
    """The knob x metric table; a ``*`` marks an effect larger than the run's own noise."""
    header = f"{'knob':<{NAME_WIDTH}}" + "".join(
        m[: COLUMN_WIDTH - 1].rjust(COLUMN_WIDTH) for m in metrics
    )
    noise_row = f"{'(noise, 95%)':<{NAME_WIDTH}}" + "".join(
        f"{noise.get(m, math.nan):.2f}".rjust(COLUMN_WIDTH) for m in metrics
    )
    lines = [header, noise_row, "-" * len(header)]
    for item in sensitivities:
        if item.effects is None:
            lines.append(f"{item.knob.path:<{NAME_WIDTH}}  (no legal change)")
            continue
        cells = "".join(_cell(item.effects[m], noise.get(m, 0.0)) for m in metrics)
        lines.append(f"{item.knob.path:<{NAME_WIDTH}}{cells}")
    return "\n".join(lines)


def strongest(sensitivities: Sequence[Sensitivity], metric: str, count: int) -> list[Sensitivity]:
    """The ``count`` knobs that move ``metric`` most (largest absolute effect first)."""
    movable = [s for s in sensitivities if s.effects is not None]
    return sorted(movable, key=lambda s: abs((s.effects or {})[metric]), reverse=True)[:count]
