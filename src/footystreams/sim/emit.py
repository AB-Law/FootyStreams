"""Event emission: the one place events are built, so every event is validated.

The emitter numbers events (`seq`, ids), stamps the clock and a causal `EventContext` taken from
the live state, and keeps the log. Nothing here draws random numbers. Events are always built
through their Pydantic model (docs/design/11 section 6.2); there is no trusted shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from footystreams.domain.types import MatchId, PlayerId, Pos
from footystreams.events.base import EventBase, Participant
from footystreams.events.clock import match_clock
from footystreams.events.context import ContextTag, EventContext
from footystreams.events.types import MATCH_EVENT_ADAPTER, MatchEvent
from footystreams.sim.geometry import Point, frame_coordinate
from footystreams.sim.mathx import clamp
from footystreams.sim.state import MatchState

TeamLabel = Literal["home", "away", "none"]
PHASE_BUILD_UP_MAX_X = 0.40
PHASE_PROGRESSION_MAX_X = 0.67
_SIGNIFICANCE_BY_TYPE = {
    "goal": 1.0,
    "penalty": 0.6,
    "card": 0.4,
    "injury": 0.35,
    "substitution": 0.2,
    "save": 0.3,
    "shot": 0.15,
    "foul": 0.1,
    "tackle": 0.08,
    "interception": 0.06,
}
_DEFAULT_SIGNIFICANCE = 0.04
_XG_SIGNIFICANCE = 2.0


@dataclass(frozen=True, slots=True)
class Meta:
    """What every event shares besides its type-specific fields."""

    team: TeamLabel = "none"
    participants: tuple[Participant, ...] = ()
    pos: Point | None = None  # absolute, clamped into the pitch
    caused_by: str | None = None
    headline: str | None = None
    tags: tuple[ContextTag, ...] = ()


def participant(player_id: PlayerId, role: str) -> Participant:
    """Build a participant entry."""
    return Participant(player_id=player_id, role=role)


class EventEmitter:
    """Builds, numbers and stores the events of one match."""

    def __init__(self, match_id: MatchId) -> None:
        """Start an empty log for `match_id`."""
        self._match_id = match_id
        self._events: list[MatchEvent] = []
        self._pending = 0

    @property
    def events(self) -> list[MatchEvent]:
        """Every event emitted so far, in order."""
        return self._events

    def drain(self) -> list[MatchEvent]:
        """Return the events emitted since the last drain (so the generator can yield them)."""
        fresh = self._events[self._pending :]
        self._pending = len(self._events)
        return fresh

    def emit(
        self, state: MatchState, event_class: type[EventBase], meta: Meta, **fields: object
    ) -> str:
        """Build one validated event, append it to the log and return its id."""
        seq = len(self._events)
        event_id = f"{self._match_id}:{seq:05d}"
        event_type = str(event_class.model_fields["type"].default)
        event = MATCH_EVENT_ADAPTER.validate_python(
            {
                "id": event_id,
                "match_id": self._match_id,
                "seq": seq,
                "tick": state.tick,
                "type": event_type,
                "clock": match_clock(state.period, int(state.t_period)),
                "team": meta.team,
                "participants": meta.participants,
                "pos": _position(meta.pos),
                "caused_by": meta.caused_by,
                "chain_id": str(state.chain),
                "ctx": _context(state, event_type, meta, fields),
                **fields,
            }
        )
        self._events.append(event)
        return event_id


def _position(point: Point | None) -> Pos | None:
    if point is None:
        return None
    return Pos(x=clamp(point[0], 0.0, 1.0), y=clamp(point[1], 0.0, 1.0))


def phase_of(state: MatchState) -> str:
    """Name where play is, from the ball's position in the possessing team's frame."""
    frame_x = frame_coordinate(state.ball_x, state.attackers.attack_dir)
    if frame_x < PHASE_BUILD_UP_MAX_X:
        return "build_up"
    return "progression" if frame_x < PHASE_PROGRESSION_MAX_X else "final_third"


def significance(event_type: str, xg: float) -> float:
    """Return how much an event matters in [0, 1]: a rule on type, lifted by shot quality."""
    base = _SIGNIFICANCE_BY_TYPE.get(event_type, _DEFAULT_SIGNIFICANCE)
    if event_type == "shot":
        base += _XG_SIGNIFICANCE * xg
    return clamp(base, 0.0, 1.0)


def _context(
    state: MatchState, event_type: str, meta: Meta, fields: dict[str, object]
) -> EventContext:
    team = state.attackers if meta.team == "none" else state.team(meta.team)
    return EventContext(
        score_home=state.home.score,
        score_away=state.away.score,
        phase=phase_of(state),
        significance=significance(event_type, _shot_quality(fields)),
        men_home=len(state.home.players),
        men_away=len(state.away.players),
        tags=meta.tags,
        headline=meta.headline,
        attack_dir=team.attack_dir,
    )


def _shot_quality(fields: dict[str, object]) -> float:
    xg = fields.get("xg", 0.0)
    return float(xg) if isinstance(xg, (int, float)) else 0.0
