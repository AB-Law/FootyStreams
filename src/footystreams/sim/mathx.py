"""Exact-arithmetic helpers shared by the simulation.

Only `+ - * /`, `sqrt` and comparisons: no `exp`, `log`, `pow` or trigonometry, so results are
bit-identical across platforms (docs/adr/0001). Never use `**` on floats here; it calls libm `pow`.
"""

from __future__ import annotations

from math import sqrt

PERCENT = 100.0  # attributes are on a 1-100 scale; divide by this for a 0-1 share
_HALF = 0.5


def clamp(value: float, low: float, high: float) -> float:
    """Limit `value` to the closed interval [low, high]."""
    return low if value < low else high if value > high else value


def squash(z: float) -> float:
    """Return the universal bounded S-curve 0.5 + 0.5*z/sqrt(1+z*z), in (0, 1).

    Monotone, symmetric around (0, 0.5) and exact with sqrt, which is why it replaces the logistic.
    """
    return 0.5 + 0.5 * z / sqrt(1.0 + z * z)


def lerp(start: float, end: float, fraction: float) -> float:
    """Return the point `fraction` of the way from `start` to `end`."""
    return start + (end - start) * fraction


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the Euclidean distance between two points, using sqrt only."""
    dx = x2 - x1
    dy = y2 - y1
    return sqrt(dx * dx + dy * dy)


def rational_weight(utility: float, best: float, sharpness: float, floor: float) -> float:
    """Return a positive choice weight that falls as `utility` drops below `best`.

    `(1 + sharpness*(utility - best))` raised to the fourth power by repeated multiplication, with
    a floor: a monotone, exactly reproducible stand-in for the softmax exponential.
    """
    base = max(floor, 1.0 + sharpness * (utility - best))
    square = base * base
    return square * square


def signed_unit(fraction: float) -> float:
    """Map a fraction in [0, 1] onto [-1, 1] (0.5 becomes 0); used for symmetric noise."""
    return (fraction - _HALF) * 2.0
