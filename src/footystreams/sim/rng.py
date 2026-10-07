"""SimRng: the only source of randomness in the simulation.

A xoshiro256** generator seeded through splitmix64, written with integer operations only, so the
stream is identical on every platform and Python version (docs/adr/0001, docs/design/02 section 13).
Named sub-streams are derived with `fork(label)`; a stream never reads another stream's state, so
changing how often one concern draws cannot reshuffle another.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

MASK64 = (1 << 64) - 1
_SPLITMIX_INCREMENT = 0x9E3779B97F4A7C15
_SPLITMIX_MIX_1 = 0xBF58476D1CE4E5B9
_SPLITMIX_MIX_2 = 0x94D049BB133111EB
_UNIT_STEP = 1.0 / 9007199254740992.0  # 2**-53: exact, so u() is exactly (next >> 11) * step
_GAUSS_TERMS = 4
_GAUSS_SCALE = 1.7320508075688772  # sqrt(3): unit variance for a sum of four uniforms minus two
_FORK_DIGEST_BYTES = 8


def splitmix64(state: int) -> tuple[int, int]:
    """Advance a splitmix64 state and return `(new_state, output)`; used to seed the generator."""
    state = (state + _SPLITMIX_INCREMENT) & MASK64
    mixed = ((state ^ (state >> 30)) * _SPLITMIX_MIX_1) & MASK64
    mixed = ((mixed ^ (mixed >> 27)) * _SPLITMIX_MIX_2) & MASK64
    return state, mixed ^ (mixed >> 31)


def _rotate_left(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (64 - shift))) & MASK64


class SimRng:
    """Deterministic random stream with a draw counter (used by stream-isolation tests)."""

    __slots__ = ("_s0", "_s1", "_s2", "_s3", "draws", "seed")

    def __init__(self, seed: int) -> None:
        """Seed the generator; any integer is accepted (negatives wrap modulo 2**64)."""
        self.seed = seed
        self.draws = 0
        state = seed & MASK64
        state, self._s0 = splitmix64(state)
        state, self._s1 = splitmix64(state)
        state, self._s2 = splitmix64(state)
        _, self._s3 = splitmix64(state)

    def next_u64(self) -> int:
        """Return the next 64 random bits."""
        s0, s1, s2, s3 = self._s0, self._s1, self._s2, self._s3
        result = (_rotate_left((s1 * 5) & MASK64, 7) * 9) & MASK64
        shifted = (s1 << 17) & MASK64
        s2 ^= s0
        s3 ^= s1
        s1 ^= s2
        s0 ^= s3
        s2 ^= shifted
        s3 = _rotate_left(s3, 45)
        self._s0, self._s1, self._s2, self._s3 = s0, s1, s2, s3
        self.draws += 1
        return result

    def u(self) -> float:
        """Return a uniform float in [0, 1) with 53 random bits."""
        return (self.next_u64() >> 11) * _UNIT_STEP

    def u_int(self, bound: int) -> int:
        """Return a uniform integer in [0, bound); `bound` must be positive."""
        if bound <= 0:
            msg = f"u_int bound must be positive, got {bound}"
            raise ValueError(msg)
        return int(self.u() * bound)

    def bernoulli(self, probability: float) -> bool:
        """Return True with the given probability (always consumes exactly one draw)."""
        return self.u() < probability

    def gauss(self) -> float:
        """Return an approximately standard-normal value (Irwin-Hall, bounded to +-3.47)."""
        total = 0.0
        for _ in range(_GAUSS_TERMS):
            total += self.u()
        return (total - _GAUSS_TERMS / 2) * _GAUSS_SCALE

    def choice_weighted(self, weights: Sequence[float]) -> int:
        """Return an index drawn proportionally to non-negative `weights` (one draw)."""
        total = sum(weights)
        if total <= 0.0:
            msg = "choice_weighted needs a positive total weight"
            raise ValueError(msg)
        threshold = self.u() * total
        running = 0.0
        for index, weight in enumerate(weights):
            running += weight
            if threshold < running:
                return index
        return len(weights) - 1

    def fork(self, label: str) -> SimRng:
        """Derive an independent child stream named `label` (same seed + label => same stream)."""
        digest = hashlib.blake2b(
            f"{self.seed}:{label}".encode(), digest_size=_FORK_DIGEST_BYTES
        ).digest()
        return SimRng(int.from_bytes(digest, "big"))
