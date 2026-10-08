"""Who was on the pitch and for how long: minutes, starts and the players who got hurt.

A spell runs from the moment a player starts or comes on to the moment he is substituted, sent
off or leaves injured with no replacement (an injury followed directly by the matching
substitution is the substitution's departure). Pure fold over the events and the lineups.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.match import MatchSetup
from footystreams.domain.types import PlayerId
from footystreams.events.base import MatchClock
from footystreams.events.clock import period_elapsed_s
from footystreams.events.discipline import CardEvent, InjuryEvent, SubstitutionEvent
from footystreams.events.types import MatchEvent

DISMISSALS = ("red", "second_yellow")


@dataclass(frozen=True, slots=True)
class Spell:
    """One player's time on the pitch, in playing seconds since kick-off."""

    start_s: int
    end_s: int
    started: bool

    @property
    def minutes(self) -> int:
        """Whole minutes played (rounded to the nearest)."""
        return round((self.end_s - self.start_s) / 60)


def injured_off_unreplaced(events: Sequence[MatchEvent], position: int) -> bool:
    """True when the event is an injury that takes the player off and no change follows it."""
    event = events[position]
    if not isinstance(event, InjuryEvent) or event.can_continue:
        return False
    following = events[position + 1] if position + 1 < len(events) else None
    return not (
        isinstance(following, SubstitutionEvent) and following.player_off_id == event.player_id
    )


def leaver(events: Sequence[MatchEvent], position: int) -> PlayerId | None:
    """Return the player who leaves the pitch at this event, if anyone does."""
    event = events[position]
    if isinstance(event, SubstitutionEvent):
        return event.player_off_id
    if isinstance(event, CardEvent) and event.colour in DISMISSALS:
        return event.player_id
    if isinstance(event, InjuryEvent) and injured_off_unreplaced(events, position):
        return event.player_id
    return None


def _period_lengths(events: Sequence[MatchEvent]) -> dict[int, int]:
    """How long each period really ran: the clock of its last event, stoppage time included."""
    return {event.clock.period: period_elapsed_s(event.clock) for event in events}


def _playing_second(clock: MatchClock, lengths: dict[int, int]) -> int:
    """Playing seconds since kick-off: the periods before this one at their real length.

    `match_elapsed_s` counts every earlier period at its nominal length, so a second-half clock
    could read earlier than a first-half stoppage-time one and a spell could end before it began.
    """
    before = sum(length for period, length in lengths.items() if period < clock.period)
    return before + period_elapsed_s(clock)


def player_spells(
    events: Sequence[MatchEvent], setup: MatchSetup, match_end_s: int
) -> dict[PlayerId, Spell]:
    """Return a spell for every player who took part (starters first, then those who came on)."""
    lengths = _period_lengths(events)
    open_spells: dict[PlayerId, tuple[int, bool]] = {
        slot.player_id: (0, True) for sheet in (setup.home, setup.away) for slot in sheet.lineup
    }
    closed: dict[PlayerId, Spell] = {}
    for position, event in enumerate(events):
        moment = _playing_second(event.clock, lengths)
        gone = leaver(events, position)
        if gone is not None and gone in open_spells:
            start, started = open_spells.pop(gone)
            closed[gone] = Spell(start, moment, started)
        if isinstance(event, SubstitutionEvent):
            open_spells[event.player_on_id] = (moment, False)
    for player_id, (start, started) in open_spells.items():
        closed[player_id] = Spell(start, match_end_s, started)
    return closed


def injured_players(events: Sequence[MatchEvent]) -> frozenset[PlayerId]:
    """Return everyone who was the victim of an injury event."""
    return frozenset(event.player_id for event in events if isinstance(event, InjuryEvent))
