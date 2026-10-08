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
from dataclasses import dataclass

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


def sweep(
    play: Play,
    base: SimConfig,
    knobs: Sequence[Knob],
    targets: Mapping[str, Target],
    relative: float = DEFAULT_RELATIVE_STEP,
) -> list[Sensitivity]:
    """Replay the scenarios with every knob nudged down and up; ``targets`` pick the metrics."""
    names = list(targets)
    base_values = _values(play(base), names)
    results = []
    for knob in knobs:
        sides = []
        for multiplier in (1.0 - relative, 1.0 + relative):
            config = _config_at(base, knob, multiplier)
            sides.append(None if config is None else _values(play(config), names))
        results.append(Sensitivity(knob, _effects(sides[0], sides[1], base_values, targets)))
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
