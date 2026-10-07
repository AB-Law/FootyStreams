"""The two sides of a match and the helper to flip between them."""

from __future__ import annotations

from typing import Literal

Side = Literal["home", "away"]


def opposite(side: Side) -> Side:
    """Return the other side."""
    return "away" if side == "home" else "home"
