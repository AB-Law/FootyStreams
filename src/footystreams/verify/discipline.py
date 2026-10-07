"""Invariants about cards and the players on the pitch (M07 in part, M11).

M07 a player sent off, substituted off or injured off never appears in a later event
M11 card logic: a second booking is a second_yellow, nobody is carded after dismissal, and every
    event's context counts the men on the pitch correctly
"""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.types import PlayerId
from footystreams.events.discipline import CardEvent, InjuryEvent, SubstitutionEvent
from footystreams.events.types import MatchEvent
from footystreams.verify.index import players_in
from footystreams.verify.violation import Violation

TEAM_SIZE = 11
DISMISSALS = ("red", "second_yellow")


def injured_off_unreplaced(events: Sequence[MatchEvent], position: int) -> bool:
    """True when the event is an injury that takes the player off and no change follows it."""
    event = events[position]
    if not isinstance(event, InjuryEvent) or event.can_continue:
        return False
    following = events[position + 1] if position + 1 < len(events) else None
    return not (
        isinstance(following, SubstitutionEvent) and following.player_off_id == event.player_id
    )


def _leaver(events: Sequence[MatchEvent], position: int) -> PlayerId | None:
    """Return the player who leaves the pitch at this event, if anyone does."""
    event = events[position]
    if isinstance(event, CardEvent) and event.colour in DISMISSALS:
        return event.player_id
    if isinstance(event, SubstitutionEvent):
        return event.player_off_id
    if isinstance(event, InjuryEvent) and injured_off_unreplaced(events, position):
        return event.player_id
    return None


def check_dismissed_players_stay_off(events: Sequence[MatchEvent]) -> list[Violation]:
    """M07: once a player has left the pitch, he is never named again."""
    found: list[Violation] = []
    gone: set[PlayerId] = set()
    for position, event in enumerate(events):
        found.extend(
            Violation("M07", f"{player} appears after leaving the pitch", event.id)
            for player in sorted(players_in(event) & gone)
        )
        leaver = _leaver(events, position)
        if leaver is not None:
            gone.add(leaver)
    return found


def _card_problem(
    event: CardEvent, yellows: dict[PlayerId, int], gone: set[PlayerId]
) -> str | None:
    """Return what is wrong with this card given the player's history, if anything."""
    previous = yellows.get(event.player_id, 0)
    if event.player_id in gone:
        return "card shown to a player already sent off"
    if event.colour == "yellow" and previous >= 1:
        return "second booking must be a second_yellow"
    if event.colour == "second_yellow" and previous != 1:
        return f"second_yellow with {previous} earlier yellow cards"
    return None


def check_card_logic(events: Sequence[MatchEvent]) -> list[Violation]:
    """M11: yellow counts, second yellows and dismissals are consistent."""
    found: list[Violation] = []
    yellows: dict[PlayerId, int] = {}
    gone: set[PlayerId] = set()
    for event in events:
        if not isinstance(event, CardEvent):
            continue
        problem = _card_problem(event, yellows, gone)
        if problem is not None:
            found.append(Violation("M11", problem, event.id))
        if event.colour != "red":
            yellows[event.player_id] = yellows.get(event.player_id, 0) + 1
        if event.colour in DISMISSALS:
            gone.add(event.player_id)
    return found


def check_men_counts(events: Sequence[MatchEvent]) -> list[Violation]:
    """M11: the men count is 11 minus the dismissals and unreplaced injuries so far."""
    found: list[Violation] = []
    off = {"home": 0, "away": 0}
    for position, event in enumerate(events):
        leaves = isinstance(event, CardEvent) and event.colour in DISMISSALS
        if (leaves or injured_off_unreplaced(events, position)) and event.team in off:
            off[event.team] += 1
        expected = (TEAM_SIZE - off["home"], TEAM_SIZE - off["away"])
        if (event.ctx.men_home, event.ctx.men_away) != expected:
            shown = f"{event.ctx.men_home}-{event.ctx.men_away}"
            found.append(Violation("M11", f"men {shown}, expected {expected}", event.id))
    return found
