"""Pass network, zone flow, shot map and the expected-value totals, recomputed from the log."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from footystreams.domain.types import PlayerId
from footystreams.events.derive.maps import pass_matrix, shot_map, zone_pass_flow
from footystreams.events.open_play import PassEvent, ShotEvent
from footystreams.events.summary_rows import PassLink, ShotPoint, ZoneFlow
from footystreams.events.types import MatchEvent

__all__ = [
    "pass_network",
    "shot_locations",
    "xa_totals",
    "xg_totals",
    "xt_totals",
    "zone_flow",
]

_ROUND = 4


def pass_network(events: Sequence[MatchEvent]) -> tuple[PassLink, ...]:
    """Return completed passes passer -> receiver (the summary's `pass_matrix`)."""
    return pass_matrix(events)


def zone_flow(events: Sequence[MatchEvent]) -> tuple[ZoneFlow, ...]:
    """Return completed passes between 12 x 8 grid zones (the summary's `zone_pass_flow`)."""
    return zone_pass_flow(events)


def shot_locations(events: Sequence[MatchEvent]) -> tuple[ShotPoint, ...]:
    """Return every shot with position, xG and outcome (the summary's `shot_map`)."""
    return shot_map(events)


def xg_totals(events: Sequence[MatchEvent]) -> dict[str, float]:
    """Return total xG by team label ("home", "away")."""
    totals = {"home": 0.0, "away": 0.0}
    for event in events:
        if isinstance(event, ShotEvent) and event.team in totals:
            totals[event.team] += event.xg
    return {team: round(value, _ROUND) for team, value in totals.items()}


def xa_totals(events: Sequence[MatchEvent]) -> dict[PlayerId, float]:
    """Return expected assists: the xG of the shots each player set up, by player."""
    totals: defaultdict[PlayerId, float] = defaultdict(float)
    for event in events:
        if isinstance(event, ShotEvent) and event.assist_id is not None:
            totals[event.assist_id] += event.xg
    return {player: round(value, _ROUND) for player, value in sorted(totals.items())}


def xt_totals(events: Sequence[MatchEvent]) -> dict[PlayerId, float]:
    """Return expected threat: the threat gained by each player's completed passes."""
    totals: defaultdict[PlayerId, float] = defaultdict(float)
    for event in events:
        if isinstance(event, PassEvent) and event.outcome == "complete":
            totals[event.from_player_id] += event.xt_gain
    return {player: round(value, _ROUND) for player, value in sorted(totals.items())}
