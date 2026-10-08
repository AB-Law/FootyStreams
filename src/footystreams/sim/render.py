"""Plain deterministic text rendering of a match: a play-by-play line per event and a summary.

This is a formatter, not commentary: it turns structured events into fixed English templates for
the `sim` CLI and for debugging. It has no I/O and no randomness.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from footystreams.domain.match import MatchSetup
from footystreams.domain.types import PlayerId
from footystreams.events.base import EventBase, MatchClock
from footystreams.events.discipline import CardEvent, FoulEvent, InjuryEvent, SubstitutionEvent
from footystreams.events.open_play import (
    ClearanceEvent,
    DribbleEvent,
    GoalEvent,
    InterceptionEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.restarts import CornerEvent, GoalKickEvent, PenaltyEvent, ThrowInEvent
from footystreams.events.structure import (
    AddedTimeEvent,
    FulltimeEvent,
    HalftimeEvent,
    KickoffEvent,
)
from footystreams.events.summary import MatchSummary, TeamStats
from footystreams.events.types import MatchEvent

KEY_SIGNIFICANCE = 0.25
SECOND_PERIOD = 2


class Verbosity(StrEnum):
    """How much of the match to print."""

    KEY = "key"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class Names:
    """Id -> display name and club codes for one match."""

    players: Mapping[PlayerId, str]
    home_code: str
    away_code: str

    def player(self, player_id: PlayerId | None) -> str:
        """Return `Name` for a player id (the id itself when unknown)."""
        return "?" if player_id is None else self.players.get(player_id, str(player_id))

    def code(self, team: str) -> str:
        """Return the club code for a side label."""
        return self.home_code if team == "home" else self.away_code if team == "away" else "-"


def names_for(setup: MatchSetup) -> Names:
    """Collect display names and codes from both sheets of a setup."""
    players = {
        pid: snap.known_as
        for sheet in (setup.home, setup.away)
        for pid, snap in sheet.squad.items()
    }
    return Names(players, setup.home.club.short_code, setup.away.club.short_code)


def clock_text(clock: MatchClock) -> str:
    """Return the displayed time: `61'` or `45+2'`."""
    return f"{clock.minute}+{clock.stoppage}'" if clock.stoppage else f"{clock.minute}'"


def _who(names: Names, team: str, player_id: PlayerId | None) -> str:
    return f"{names.player(player_id)} ({names.code(team)})"


def _score(event: EventBase, names: Names) -> str:
    ctx = getattr(event, "ctx", None)
    if ctx is None:
        return ""
    return f"{names.home_code} {ctx.score_home}-{ctx.score_away} {names.away_code}"


Formatter = Callable[[MatchEvent, Names], str]


def _goal(event: MatchEvent, names: Names) -> str:
    assert isinstance(event, GoalEvent)  # noqa: S101 - narrows for the type checker
    assist = f" (assist {names.player(event.assist_id)})" if event.assist_id else ""
    return f"GOAL! {_who(names, event.team, event.scorer_id)}{assist}  {_score(event, names)}"


def _shot(event: MatchEvent, names: Names) -> str:
    assert isinstance(event, ShotEvent)  # noqa: S101
    who = _who(names, event.team, event.player_id)
    return f"Shot by {who}, xG {event.xg:.2f}: {event.outcome.replace('_', ' ')}"


def _pass(event: MatchEvent, names: Names) -> str:
    assert isinstance(event, PassEvent)  # noqa: S101
    target = names.player(event.to_player_id)
    passer = names.player(event.from_player_id)
    return f"Pass {passer} -> {target} ({event.outcome}, {event.length_m:.0f} m)"


def _simple(template: str, field: str) -> Formatter:
    def format_event(event: MatchEvent, names: Names) -> str:
        return template.format(who=_who(names, event.team, getattr(event, field)))

    return format_event


def _kickoff(event: MatchEvent, names: Names) -> str:  # noqa: ARG001 - formatter signature
    assert isinstance(event, KickoffEvent)  # noqa: S101
    return f"Kick-off ({'second' if event.period == SECOND_PERIOD else 'first'} half)"


def _halftime(event: MatchEvent, names: Names) -> str:
    return f"Half-time  {_score(event, names)}"


def _fulltime(event: MatchEvent, names: Names) -> str:
    return f"Full-time  {_score(event, names)}"


def _added_time(event: MatchEvent, names: Names) -> str:  # noqa: ARG001 - formatter signature
    assert isinstance(event, AddedTimeEvent)  # noqa: S101
    return f"{event.minutes} minutes of added time"


def _substitution(event: MatchEvent, names: Names) -> str:
    assert isinstance(event, SubstitutionEvent)  # noqa: S101
    on, off = names.player(event.player_on_id), names.player(event.player_off_id)
    return f"Substitution: {on} on for {off}"


_FORMATTERS: dict[type, Formatter] = {
    GoalEvent: _goal,
    ShotEvent: _shot,
    PassEvent: _pass,
    KickoffEvent: _kickoff,
    HalftimeEvent: _halftime,
    FulltimeEvent: _fulltime,
    AddedTimeEvent: _added_time,
    SubstitutionEvent: _substitution,
    SaveEvent: _simple("Save by {who}", "keeper_id"),
    DribbleEvent: _simple("Dribble by {who}", "player_id"),
    TackleEvent: _simple("Tackle by {who}", "player_id"),
    InterceptionEvent: _simple("Interception by {who}", "player_id"),
    ClearanceEvent: _simple("Clearance by {who}", "player_id"),
    CardEvent: _simple("Card for {who}", "player_id"),
    InjuryEvent: _simple("Injury to {who}", "player_id"),
    FoulEvent: _simple("Foul by {who}", "fouler_id"),
    ThrowInEvent: _simple("Throw-in: {who}", "taker_id"),
    GoalKickEvent: _simple("Goal kick: {who}", "taker_id"),
    CornerEvent: _simple("Corner: {who}", "taker_id"),
    PenaltyEvent: _simple("Penalty: {who}", "taker_id"),
}


def render_event(event: MatchEvent, names: Names) -> str:
    """Return one play-by-play line for an event."""
    text = _FORMATTERS.get(type(event), _fallback)(event, names)
    return f"{clock_text(event.clock):>7} {text}"


def _fallback(event: MatchEvent, names: Names) -> str:  # noqa: ARG001 - same signature as formatters
    return event.type.replace("_", " ")


def is_key_event(event: MatchEvent) -> bool:
    """True for events a viewer would call key: significant, or match structure."""
    if event.type in {"kickoff", "halftime", "fulltime", "added_time", "match_summary"}:
        return True
    ctx = getattr(event, "ctx", None)
    return ctx is not None and ctx.significance >= KEY_SIGNIFICANCE


def render_events(
    events: Iterable[MatchEvent], names: Names, verbosity: Verbosity
) -> Iterable[str]:
    """Yield play-by-play lines, skipping the summary event and (for KEY) minor events."""
    for event in events:
        if event.type == "match_summary":
            continue
        if verbosity is Verbosity.FULL or is_key_event(event):
            yield render_event(event, names)


_STAT_ROWS: tuple[tuple[str, Callable[[TeamStats], str]], ...] = (
    ("Possession", lambda s: f"{s.possession * 100:.0f}%"),
    ("Shots", lambda s: str(s.shots)),
    ("On target", lambda s: str(s.shots_on_target)),
    ("xG", lambda s: f"{s.xg:.2f}"),
    ("Passes", lambda s: str(s.passes)),
    ("Pass accuracy", lambda s: f"{s.pass_accuracy * 100:.0f}%"),
    ("Fouls", lambda s: str(s.fouls)),
    ("Corners", lambda s: str(s.corners)),
    ("Yellow cards", lambda s: str(s.yellows)),
    ("Red cards", lambda s: str(s.reds)),
)


def render_summary(summary: MatchSummary, names: Names) -> list[str]:
    """Return the final score line and a two-column team statistics table."""
    lines = [
        f"Final: {names.home_code} {summary.score_home}-{summary.score_away} {names.away_code}"
        f"  (HT {summary.ht_home}-{summary.ht_away})  attendance {summary.attendance:,}"
        f"  digest {summary.log_digest[:12]}",
        f"{'':<16}{names.home_code:>8}{names.away_code:>8}",
    ]
    for label, value in _STAT_ROWS:
        home, away = value(summary.team_stats_home), value(summary.team_stats_away)
        lines.append(f"{label:<16}{home:>8}{away:>8}")
    return lines
