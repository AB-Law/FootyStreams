"""Nelder-Mead simplex search: a derivative-free minimiser for a handful of noisy-ish knobs.

Plain Python on purpose (docs/design/11 s6: numpy only if profiling asks for it): the objective is
a whole simulated batch costing seconds, so the optimiser's own arithmetic is irrelevant. Points
are kept inside ``[lower, upper]`` by clamping, which suits multipliers of a default. The search is
deterministic: the starting simplex is the start point stepped along each axis in turn.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

REFLECT, EXPAND, CONTRACT, SHRINK = 1.0, 2.0, 0.5, 0.5

Objective = Callable[[Sequence[float]], float]


@dataclass(frozen=True, slots=True)
class Settings:
    """How the search moves: first step size, the box it stays in and when it stops."""

    step: float = 0.1
    lower: float = 0.0
    upper: float = 1e9
    max_evaluations: int = 200
    tolerance: float = 1e-6


@dataclass(frozen=True, slots=True)
class SearchResult:
    """The best point found, its value and how many times the objective was called."""

    point: tuple[float, ...]
    value: float
    evaluations: int


class _Search:
    def __init__(self, objective: Objective, lower: float, upper: float, budget: int) -> None:
        self._objective = objective
        self.lower, self.upper = lower, upper
        self.budget = budget
        self.evaluations = 0

    def clamp(self, point: Sequence[float]) -> tuple[float, ...]:
        return tuple(min(max(x, self.lower), self.upper) for x in point)

    def value(self, point: tuple[float, ...]) -> float:
        self.evaluations += 1
        return self._objective(point)

    @property
    def exhausted(self) -> bool:
        return self.evaluations >= self.budget


def _centroid(points: Sequence[tuple[float, ...]]) -> tuple[float, ...]:
    return tuple(sum(p[i] for p in points) / len(points) for i in range(len(points[0])))


def _towards(centre: Sequence[float], other: Sequence[float], factor: float) -> list[float]:
    return [c + factor * (o - c) for c, o in zip(centre, other, strict=True)]


def _initial(
    start: tuple[float, ...], step: float, search: _Search
) -> list[tuple[tuple[float, ...], float]]:
    simplex = [(start, search.value(start))]
    for axis in range(len(start)):
        if search.exhausted:
            break
        moved = list(start)
        moved[axis] += step if moved[axis] + step <= search.upper else -step
        point = search.clamp(moved)
        simplex.append((point, search.value(point)))
    return simplex


def _iterate(simplex: list[tuple[tuple[float, ...], float]], search: _Search) -> None:
    """One Nelder-Mead step, in place; ``simplex`` is sorted best first on entry and exit."""
    worst_point, worst_value = simplex[-1]
    centre = _centroid([p for p, _ in simplex[:-1]])
    reflected = search.clamp(_towards(centre, worst_point, -REFLECT))
    reflected_value = search.value(reflected)
    if reflected_value < simplex[0][1] and not search.exhausted:
        expanded = search.clamp(_towards(centre, worst_point, -EXPAND))
        expanded_value = search.value(expanded)
        simplex[-1] = min(
            (expanded, expanded_value), (reflected, reflected_value), key=lambda e: e[1]
        )
    elif reflected_value < simplex[-2][1]:
        simplex[-1] = (reflected, reflected_value)
    else:
        outside = reflected_value < worst_value
        target = reflected if outside else worst_point
        contracted = search.clamp(_towards(centre, target, CONTRACT))
        contracted_value = search.value(contracted)
        if contracted_value < min(reflected_value, worst_value):
            simplex[-1] = (contracted, contracted_value)
        else:
            best = simplex[0][0]
            shrunk = [simplex[0]]
            for point, _ in simplex[1:]:
                if search.exhausted:
                    shrunk.append((point, float("inf")))
                    continue
                moved = search.clamp(_towards(best, point, SHRINK))
                shrunk.append((moved, search.value(moved)))
            simplex[:] = shrunk
    simplex.sort(key=lambda entry: entry[1])


def minimise(
    objective: Objective, start: Sequence[float], settings: Settings | None = None
) -> SearchResult:
    """Minimise ``objective`` from ``start``; stops at the budget or when the simplex is flat.

    The budget is checked between iterations, so it can be exceeded by one iteration (at most
    ``len(start) + 2`` calls).
    """
    chosen = settings or Settings()
    search = _Search(objective, chosen.lower, chosen.upper, chosen.max_evaluations)
    simplex = _initial(search.clamp(start), chosen.step, search)
    simplex.sort(key=lambda entry: entry[1])
    while not search.exhausted and len(simplex) > 1:
        if simplex[-1][1] - simplex[0][1] <= chosen.tolerance:
            break
        _iterate(simplex, search)
    best_point, best_value = simplex[0]
    return SearchResult(best_point, best_value, search.evaluations)
