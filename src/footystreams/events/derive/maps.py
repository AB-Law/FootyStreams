"""Analytics maps and timelines derived from the log: pass network, zone flow, shots, xG, momentum.

Each function reads only events, so `analytics` and `verify` can recompute exactly what the
summary carries (docs/design/03 section 5). Orderings are deterministic: sorted keys, log order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from footystreams.domain.types import PlayerId
from footystreams.events.clock import match_elapsed_s
from footystreams.events.derive.threat import frame_value, zone_of
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import PassEvent, ShotEvent
from footystreams.events.structure import FrameEvent
from footystreams.events.summary_rows import (
    KeyMoment,
    MomentumPoint,
    PassLink,
    ShotPoint,
    XgPoint,
    ZoneFlow,
)
from footystreams.events.types import MatchEvent

KEY_MOMENT_MIN_SIGNIFICANCE = 0.5
SECONDS_PER_SAMPLE = 60
_ROUND = 4


def pass_matrix(events: Sequence[MatchEvent]) -> tuple[PassLink, ...]:
    """Return completed passes passer -> receiver, sorted by passer then receiver."""
    counts: Counter[tuple[PlayerId, PlayerId]] = Counter()
    for event in events:
        if isinstance(event, PassEvent) and event.outcome == "complete" and event.to_player_id:
            counts[(event.from_player_id, event.to_player_id)] += 1
    return tuple(
        PassLink(passer_id=a, receiver_id=b, count=n) for (a, b), n in sorted(counts.items())
    )


def zone_pass_flow(events: Sequence[MatchEvent]) -> tuple[ZoneFlow, ...]:
    """Return completed passes between grid zones in the passing team's frame."""
    counts: Counter[tuple[str, int, int]] = Counter()
    for event in events:
        if not (
            isinstance(event, PassEvent)
            and event.outcome == "complete"
            and event.pos is not None
            and event.end_pos is not None
            and event.team in ("home", "away")
        ):
            continue
        direction = event.ctx.attack_dir
        origin = zone_of(frame_value(event.pos.x, direction), frame_value(event.pos.y, direction))
        target = zone_of(
            frame_value(event.end_pos.x, direction), frame_value(event.end_pos.y, direction)
        )
        counts[(event.team, origin, target)] += 1
    return tuple(
        ZoneFlow(team=team, from_zone=a, to_zone=b, count=n)  # type: ignore[arg-type]
        for (team, a, b), n in sorted(counts.items())
    )


def shot_map(events: Sequence[MatchEvent]) -> tuple[ShotPoint, ...]:
    """Return every shot with its position, xG and outcome, in log order."""
    return tuple(
        ShotPoint(
            event_id=event.id,
            team=event.team,
            x=event.pos.x,
            y=event.pos.y,
            xg=event.xg,
            outcome=event.outcome,
        )
        for event in events
        if isinstance(event, ShotEvent) and event.pos is not None and event.team != "none"
    )


def xg_timeline(events: Sequence[MatchEvent]) -> tuple[XgPoint, ...]:
    """Return cumulative xG of both sides after each shot."""
    totals = {"home": 0.0, "away": 0.0}
    points = []
    for event in events:
        if isinstance(event, ShotEvent) and event.team in totals:
            totals[event.team] += event.xg
            points.append(
                XgPoint(
                    t=match_elapsed_s(event.clock),
                    home=round(totals["home"], _ROUND),
                    away=round(totals["away"], _ROUND),
                )
            )
    return tuple(points)


def momentum_timeline(events: Sequence[MatchEvent], duration_s: int) -> tuple[MomentumPoint, ...]:
    """Return the momentum at each whole minute: that of the latest event at or before it."""
    plays = [event for event in events if not isinstance(event, FrameEvent)]
    points = []
    latest, cursor = 0.0, 0
    for sample in range(0, duration_s + 1, SECONDS_PER_SAMPLE):
        while cursor < len(plays) and match_elapsed_s(plays[cursor].clock) <= sample:
            latest = plays[cursor].ctx.momentum
            cursor += 1
        points.append(MomentumPoint(t=sample, momentum=latest))
    return tuple(points)


def key_moments(events: Sequence[MatchEvent]) -> tuple[KeyMoment, ...]:
    """Return the events worth replaying: significant ones and every dismissal."""
    return tuple(
        KeyMoment(
            event_id=event.id,
            kind=event.type,
            significance=event.ctx.significance,
            t=match_elapsed_s(event.clock),
        )
        for event in events
        if not isinstance(event, FrameEvent)
        and (
            event.ctx.significance >= KEY_MOMENT_MIN_SIGNIFICANCE
            or (isinstance(event, CardEvent) and event.colour != "yellow")
        )
    )
