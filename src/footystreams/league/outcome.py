"""How a side's match ended, from that side's point of view."""

from __future__ import annotations

from enum import StrEnum


class Outcome(StrEnum):
    """Win, draw or loss."""

    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"


def outcome_for(scored: int, conceded: int) -> Outcome:
    """The result of a side that scored ``scored`` and conceded ``conceded``."""
    if scored > conceded:
        return Outcome.WIN
    return Outcome.DRAW if scored == conceded else Outcome.LOSS
