"""Deterministic id minting: a per-kind counter rendered in base 36."""

from __future__ import annotations

from collections import Counter

from footystreams.domain.types import ID_PREFIXES

_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
ID_WIDTH = 5


def base36(number: int, width: int = ID_WIDTH) -> str:
    """Render a non-negative int in lower-case base 36, zero-padded to ``width``."""
    if number < 0:
        msg = f"cannot render negative number {number} as an id"
        raise ValueError(msg)
    digits = ""
    value = number
    while value:
        value, remainder = divmod(value, len(_BASE36))
        digits = _BASE36[remainder] + digits
    return digits.rjust(width, "0")


class IdMint:
    """Hands out ``<prefix><counter>`` ids, one counter per entity kind.

    Mutable by design (it counts); one mint is threaded through a whole generation run so ids are
    unique and the same seed always produces the same ids in the same order.
    """

    def __init__(self) -> None:
        """Start every kind's counter at zero."""
        self._counts: Counter[str] = Counter()

    def next(self, kind: str) -> str:
        """Mint the next id of ``kind`` (a key of ``ID_PREFIXES``, e.g. ``player``)."""
        try:
            prefix = ID_PREFIXES[kind]
        except KeyError as error:
            msg = f"unknown id kind {kind!r}"
            raise ValueError(msg) from error
        self._counts[kind] += 1
        return f"{prefix}{base36(self._counts[kind])}"

    def minted(self, kind: str) -> int:
        """How many ids of ``kind`` have been minted so far."""
        return self._counts[kind]
