"""Fit chosen knobs to a profile: minimise the weighted loss over a fixed batch of matches.

The search runs on multipliers of the default value (1.0 is "unchanged"), inside bounds, with
Nelder-Mead. Every evaluation replays the same scenarios, so the objective is a deterministic
function of the knobs; that makes the result reproducible but also means it can fit the *batch*
rather than the league, which is why the CLI re-measures the winner on fresh seeds. The outcome is
a *candidate* partial config for a human to review: nothing here changes a shipped default.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import yaml

from footystreams.balance import nelder_mead, overrides
from footystreams.balance.evaluate import MAX_LOSS, evaluate, total_loss
from footystreams.balance.knobs import Knob, with_multipliers
from footystreams.balance.sample import MatchSample
from footystreams.balance.targets import Target
from footystreams.sim.config import SimConfig

DEFAULT_BOUNDS = (0.5, 2.0)
DEFAULT_STEP = 0.15
SIGNIFICANT_DIGITS = 4
UNCHANGED = 1e-9

Play = Callable[[SimConfig], Sequence[MatchSample]]


@dataclass(frozen=True, slots=True)
class FitSettings:
    """The search budget and range: multiplier bounds, evaluations, restarts, seed, first step."""

    bounds: tuple[float, float] = DEFAULT_BOUNDS
    max_evaluations: int = 200
    restarts: int = 1
    seed: int = 1
    step: float = DEFAULT_STEP


@dataclass(frozen=True, slots=True)
class FitResult:
    """The candidate overrides, the loss with and without them, and the work it took."""

    overrides: Mapping[str, object]
    loss_before: float
    loss_after: float
    evaluations: int


def _loss(play: Play, config: SimConfig, targets: Mapping[str, Target]) -> float:
    return total_loss(evaluate(play(config), targets))


def _round(value: float) -> float:
    return float(f"{value:.{SIGNIFICANT_DIGITS}g}")


def candidate_overrides(
    chosen: Sequence[Knob], multipliers: Mapping[str, float]
) -> dict[str, object]:
    """The nested partial config for the knobs that moved, at four significant digits."""
    changes = [
        overrides.nest(knob.path, _round(knob.default * multipliers[knob.path]))
        for knob in chosen
        if abs(multipliers[knob.path] - 1.0) > UNCHANGED
    ]
    return overrides.combine(changes)


def _restart_points(
    best: Sequence[float], restarts: int, seed: int, step: float, bounds: tuple[float, float]
) -> list[tuple[float, ...]]:
    """Restart 0 is the start itself; later ones jitter the incumbent (seeded, so reproducible)."""
    generator = random.Random(seed)  # noqa: S311 - a search jitter, not a secret
    points = [tuple(best)]
    points.extend(
        tuple(min(max(x + generator.uniform(-step, step), bounds[0]), bounds[1]) for x in best)
        for _ in range(restarts - 1)
    )
    return points


def fit(
    play: Play,
    base: SimConfig,
    chosen: Sequence[Knob],
    targets: Mapping[str, Target],
    settings: FitSettings | None = None,
) -> FitResult:
    """Search the knobs for the lowest loss; the budget is split evenly over the restarts."""
    options = settings or FitSettings()
    paths = [knob.path for knob in chosen]
    invalid = MAX_LOSS * sum(target.weight for target in targets.values())

    def objective(point: Sequence[float]) -> float:
        try:
            config = with_multipliers(base, chosen, dict(zip(paths, point, strict=True)))
        except ValueError:
            return invalid
        return _loss(play, config, targets)

    start = [1.0] * len(chosen)
    loss_before = objective(start)
    best = nelder_mead.SearchResult(tuple(start), loss_before, 1)
    evaluations = best.evaluations
    search = nelder_mead.Settings(
        step=options.step,
        lower=options.bounds[0],
        upper=options.bounds[1],
        max_evaluations=max(options.max_evaluations // options.restarts, 1),
    )
    for first in _restart_points(
        start, options.restarts, options.seed, options.step, options.bounds
    ):
        found = nelder_mead.minimise(objective, first, search)
        evaluations += found.evaluations
        best = min(best, found, key=lambda result: result.value)
    chosen_overrides = candidate_overrides(chosen, dict(zip(paths, best.point, strict=True)))
    loss_after = _loss(play, overrides.apply(base, chosen_overrides), targets)
    return FitResult(chosen_overrides, loss_before, loss_after, evaluations + 1)


def format_candidate(found: FitResult, notes: Sequence[str]) -> str:
    """The candidate as YAML for ``--config``, headed by comments saying what it is."""
    header = [f"# {line}" for line in notes]
    header.append(f"# loss {found.loss_before:.3f} -> {found.loss_after:.3f}")
    body = yaml.safe_dump(dict(found.overrides), sort_keys=False) if found.overrides else "{}\n"
    return "\n".join(header) + "\n" + body
