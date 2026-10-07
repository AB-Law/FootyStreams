"""Deterministic id minting: a per-kind counter rendered in base 36.

Lives in domain because both the seed generators and the league layer mint ids, and neither may
import the other.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping

from footystreams.domain.types import ID_PREFIXES

_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
ID_WIDTH = 5
DERIVED_WIDTH = 10
DERIVED_BYTES = 8
# Kinds minted by the seed and league layers that have no entity prefix in domain.types.
EXTRA_PREFIXES: Mapping[str, str] = {
    "ledger": "led_",
    "world_event": "evt_",
    "modifier": "mod_",
    "window": "win_",
    "listing": "lst_",
    "bid": "bid_",
    "offer": "ofr_",
    "transfer": "trf_",
    "scout_report": "sct_",
    "season_record": "rec_",
}
PREFIXES: Mapping[str, str] = {**ID_PREFIXES, **EXTRA_PREFIXES}


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

    def __init__(self, counts: Mapping[str, int] | None = None) -> None:
        """Start every kind's counter at zero, or resume from saved counts."""
        self._counts: Counter[str] = Counter(counts or {})

    def next(self, kind: str) -> str:
        """Mint the next id of ``kind`` (a key of ``ID_PREFIXES``, e.g. ``player``)."""
        try:
            prefix = PREFIXES[kind]
        except KeyError as error:
            msg = f"unknown id kind {kind!r}"
            raise ValueError(msg) from error
        self._counts[kind] += 1
        return f"{prefix}{base36(self._counts[kind])}"

    def snapshot(self) -> dict[str, int]:
        """The counters, so a discarded attempt can be undone with ``restore``."""
        return dict(self._counts)

    def restore(self, counts: Mapping[str, int]) -> None:
        """Reset the counters to a previous ``snapshot``."""
        self._counts = Counter(counts)

    def minted(self, kind: str) -> int:
        """How many ids of ``kind`` have been minted so far."""
        return self._counts[kind]


def derive_id(kind: str, *parts: str) -> str:
    """A stateless id for ``kind`` that depends only on ``parts`` (same parts, same id).

    The league layer mints rows from pure functions that must give the same rows when a stage is
    re-run, so it derives ids from what the row is about instead of counting.
    """
    prefix = PREFIXES[kind]
    digest = hashlib.blake2b("\x1f".join(parts).encode(), digest_size=DERIVED_BYTES).digest()
    return prefix + base36(int.from_bytes(digest, "big"), DERIVED_WIDTH)[-DERIVED_WIDTH:]
