"""Deterministic, forkable random streams for world generation and the league layer.

Why this exists: the match simulator owns its own ``SimRng`` (``sim/rng.py``); the seed and league
layers may not import ``sim``, so they share this small generator instead. The interface mirrors the
design's ``SimRng`` (``u``, ``u_int``, ``bernoulli``, ``gauss``, ``choice_weighted``, ``fork``) so
the two can be unified later. Only integer arithmetic and ``hashlib`` are used, so the output is
identical on every platform and Python version. ``random`` is banned in pure layers on purpose.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, MutableSequence, Sequence
from typing import TypeVar

T = TypeVar("T")

_MASK_64 = (1 << 64) - 1
_GOLDEN_GAMMA = 0x9E3779B97F4A7C15
_MIX_A = 0xBF58476D1CE4E5B9
_MIX_B = 0x94D049BB133111EB
_SHIFT_A, _SHIFT_B, _SHIFT_C = 30, 27, 31
_MANTISSA_SHIFT = 11  # keep the top 53 bits: the precision of a float64 mantissa
_UNIT_SCALE = 1.0 / (1 << 53)
_SEED_BYTES = 8
_IRWIN_HALL_TERMS = 4
_IRWIN_HALL_SCALE = 3**0.5  # (sum of 4 uniforms - 2) has variance 1/3; times sqrt(3) gives 1


def _mix(state: int) -> int:
    """SplitMix64 output function: scrambles one counter value into a well-spread 64-bit int."""
    value = state
    value = ((value ^ (value >> _SHIFT_A)) * _MIX_A) & _MASK_64
    value = ((value ^ (value >> _SHIFT_B)) * _MIX_B) & _MASK_64
    return value ^ (value >> _SHIFT_C)


def derive_seed(parent_seed: int, label: str) -> int:
    """Derive a child seed from a parent seed and a label (stable across platforms)."""
    digest = hashlib.blake2b(
        parent_seed.to_bytes(_SEED_BYTES, "big", signed=False) + label.encode("utf-8"),
        digest_size=_SEED_BYTES,
    ).digest()
    return int.from_bytes(digest, "big")


class WorldRng:
    """A SplitMix64 stream. Mutable by design: every draw advances the stream."""

    def __init__(self, seed: int) -> None:
        """Start a stream; negative or oversized seeds are folded into 64 bits."""
        self._seed = seed & _MASK_64
        self._state = self._seed

    @property
    def seed(self) -> int:
        """The seed this stream started from (children are derived from it, not from state)."""
        return self._seed

    def fork(self, label: str) -> WorldRng:
        """Return an independent child stream; the parent's position is not consumed."""
        return WorldRng(derive_seed(self._seed, label))

    def next_int(self) -> int:
        """Draw 64 uniformly distributed bits."""
        self._state = (self._state + _GOLDEN_GAMMA) & _MASK_64
        return _mix(self._state)

    def u(self) -> float:
        """Draw a uniform float in [0, 1)."""
        return (self.next_int() >> _MANTISSA_SHIFT) * _UNIT_SCALE

    def u_int(self, bound: int) -> int:
        """Draw an int in [0, bound). Bias is negligible for the small bounds used here."""
        if bound <= 0:
            msg = f"u_int bound must be positive, got {bound}"
            raise ValueError(msg)
        return self.next_int() % bound

    def uniform(self, low: float, high: float) -> float:
        """Draw a uniform float in [low, high)."""
        return low + (high - low) * self.u()

    def randint(self, low: int, high: int) -> int:
        """Draw an int in [low, high] (both inclusive)."""
        if high < low:
            msg = f"randint needs low <= high, got {low}..{high}"
            raise ValueError(msg)
        return low + self.u_int(high - low + 1)

    def bernoulli(self, probability: float) -> bool:
        """Return True with the given probability."""
        return self.u() < probability

    def gauss(self) -> float:
        """Draw an approximately standard normal value (Irwin-Hall; exact IEEE arithmetic only)."""
        total = sum(self.u() for _ in range(_IRWIN_HALL_TERMS))
        return (total - _IRWIN_HALL_TERMS / 2) * _IRWIN_HALL_SCALE

    def normal(self, mean: float, deviation: float) -> float:
        """Draw from a normal distribution."""
        return mean + deviation * self.gauss()

    def truncated_normal(self, mean: float, deviation: float, low: float, high: float) -> float:
        """Draw a normal value clamped into [low, high]."""
        return max(low, min(high, self.normal(mean, deviation)))

    def beta(self, alpha: int, beta: int) -> float:
        """Draw Beta(alpha, beta) for integer shapes (order statistic of alpha+beta-1 uniforms)."""
        if alpha < 1 or beta < 1:
            msg = f"beta shapes must be positive integers, got {alpha}, {beta}"
            raise ValueError(msg)
        draws = sorted(self.u() for _ in range(alpha + beta - 1))
        return draws[alpha - 1]

    def choice(self, items: Sequence[T]) -> T:
        """Pick one item uniformly."""
        if not items:
            msg = "choice from an empty sequence"
            raise ValueError(msg)
        return items[self.u_int(len(items))]

    def choice_weighted(self, weights: Mapping[T, float]) -> T:
        """Pick a key with probability proportional to its weight.

        Keys are visited in sorted-by-repr order so the result never depends on dict order.
        """
        ordered = sorted(weights.items(), key=lambda pair: repr(pair[0]))
        total = sum(weight for _, weight in ordered)
        if not ordered or total <= 0:
            msg = "choice_weighted needs at least one positive weight"
            raise ValueError(msg)
        target = self.u() * total
        running = 0.0
        for key, weight in ordered:
            running += weight
            if target < running:
                return key
        return ordered[-1][0]

    def shuffle(self, items: MutableSequence[T]) -> None:
        """Shuffle in place (Fisher-Yates)."""
        for index in range(len(items) - 1, 0, -1):
            other = self.u_int(index + 1)
            items[index], items[other] = items[other], items[index]

    def shuffled(self, items: Sequence[T]) -> list[T]:
        """Return a shuffled copy."""
        copy = list(items)
        self.shuffle(copy)
        return copy
