"""Hand-built event logs for rule tests: no simulator, every field chosen by the test."""

from __future__ import annotations

from typing import Any

from footystreams.events.base import EventBase, MatchClock
from footystreams.events.context import EventContext
from footystreams.events.types import MatchEvent

MATCH_ID = "mch_synth0001"


class LogBuilder:
    """Builds a log event by event with contiguous `seq`, matching ids and a chosen clock."""

    def __init__(self) -> None:
        """Start an empty log."""
        self.events: list[MatchEvent] = []

    def add(  # noqa: PLR0913 - a synthetic event is described by these independent knobs
        self,
        cls: type[EventBase],
        *,
        team: str = "home",
        period: int = 1,
        minute: int = 10,
        second: int = 0,
        stoppage: int = 0,
        men: tuple[int, int] = (11, 11),
        significance: float = 0.0,
        **fields: Any,
    ) -> MatchEvent:
        """Append an event of `cls` and return it (ctx carries men and significance only)."""
        seq = len(self.events)
        event = cls.model_validate(
            {
                "id": f"{MATCH_ID}:{seq:05d}",
                "match_id": MATCH_ID,
                "seq": seq,
                "tick": seq,
                "clock": MatchClock(period=period, minute=minute, second=second, stoppage=stoppage),
                "team": team,
                "ctx": EventContext(men_home=men[0], men_away=men[1], significance=significance),
                **fields,
            }
        )
        assert isinstance(event, EventBase)
        self.events.append(event)  # type: ignore[arg-type]
        return event  # type: ignore[return-value]
