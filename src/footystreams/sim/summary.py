"""Build the match summary as a pure fold over the event log.

Everything in the summary is derivable from the events (plus the setup for names and lineups), so
`verify` can recompute it and compare (invariant M14). Ratings, hooks and analytics maps are added
by later milestones.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from footystreams.domain.match import MatchSetup, SetupRef
from footystreams.domain.types import PlayerId
from footystreams.events.clock import SECONDS_PER_MINUTE, match_elapsed_s
from footystreams.events.discipline import CardEvent, FoulEvent
from footystreams.events.open_play import GoalEvent, PassEvent, ShotEvent
from footystreams.events.restarts import CornerEvent
from footystreams.events.structure import HalftimeEvent
from footystreams.events.summary import MatchSummary, PlayerMatchStats, TeamStats
from footystreams.events.types import MatchEvent

MAX_POSSESSION_INTERVAL_S = (
    30  # longer gaps are dead time (celebrations, treatment), not possession
)
_ON_TARGET = ("goal", "saved")


@dataclass(slots=True)
class _Side:
    shots: int = 0
    on_target: int = 0
    xg: float = 0.0
    passes: int = 0
    completed: int = 0
    fouls: int = 0
    corners: int = 0
    yellows: int = 0
    reds: int = 0
    possession_s: float = 0.0


@dataclass(slots=True)
class _Player:
    goals: int = 0
    assists: int = 0
    shots: int = 0
    xg: float = 0.0
    yellows: int = 0
    reds: int = 0


@dataclass(slots=True)
class _Tally:
    home: _Side = field(default_factory=_Side)
    away: _Side = field(default_factory=_Side)
    players: dict[PlayerId, _Player] = field(default_factory=dict)

    def side(self, team: str) -> _Side | None:
        return self.home if team == "home" else self.away if team == "away" else None

    def player(self, player_id: PlayerId) -> _Player:
        return self.players.setdefault(player_id, _Player())


def _on_shot(tally: _Tally, event: MatchEvent) -> None:
    assert isinstance(event, ShotEvent)  # noqa: S101 - narrows the dispatch table's type
    side = tally.side(event.team)
    player = tally.player(event.player_id)
    if side is not None:
        side.shots += 1
        side.on_target += event.outcome in _ON_TARGET
        side.xg += event.xg
    player.shots += 1
    player.xg += event.xg


def _on_goal(tally: _Tally, event: MatchEvent) -> None:
    assert isinstance(event, GoalEvent)  # noqa: S101
    tally.player(event.scorer_id).goals += 1
    if event.assist_id is not None:
        tally.player(event.assist_id).assists += 1


def _on_pass(tally: _Tally, event: MatchEvent) -> None:
    assert isinstance(event, PassEvent)  # noqa: S101
    side = tally.side(event.team)
    if side is not None:
        side.passes += 1
        side.completed += event.outcome == "complete"


def _on_foul(tally: _Tally, event: MatchEvent) -> None:
    side = tally.side(event.team)
    if side is not None:
        side.fouls += 1


def _on_corner(tally: _Tally, event: MatchEvent) -> None:
    side = tally.side(event.team)
    if side is not None:
        side.corners += 1


def _on_card(tally: _Tally, event: MatchEvent) -> None:
    assert isinstance(event, CardEvent)  # noqa: S101
    side, player = tally.side(event.team), tally.player(event.player_id)
    sent_off = event.colour != "yellow"
    if side is not None:
        side.reds += sent_off
        side.yellows += event.colour != "red"
    player.reds += sent_off
    player.yellows += event.colour != "red"


_HANDLERS: dict[type, Callable[[_Tally, MatchEvent], None]] = {
    ShotEvent: _on_shot,
    GoalEvent: _on_goal,
    PassEvent: _on_pass,
    FoulEvent: _on_foul,
    CornerEvent: _on_corner,
    CardEvent: _on_card,
}


def _attribute_possession(tally: _Tally, events: Sequence[MatchEvent]) -> None:
    """Credit each gap between events to the side that acted at its start (capped)."""
    for current, following in pairwise(events):
        side = tally.side(current.team)
        if side is None or isinstance(current, GoalEvent):
            continue
        gap = match_elapsed_s(following.clock) - match_elapsed_s(current.clock)
        side.possession_s += min(max(gap, 0), MAX_POSSESSION_INTERVAL_S)


def match_duration_s(events: Sequence[MatchEvent]) -> int:
    """Return the playing seconds of the match: the clock of the last event."""
    return match_elapsed_s(events[-1].clock) if events else 0


def halftime_score(events: Sequence[MatchEvent]) -> tuple[int, int]:
    """Return the score at the halftime event, or (0, 0) when there was none."""
    for event in events:
        if isinstance(event, HalftimeEvent):
            return event.score_home, event.score_away
    return 0, 0


def _team_stats(side: _Side, other: _Side) -> TeamStats:
    total = side.possession_s + other.possession_s
    return TeamStats(
        possession=round(side.possession_s / total, 4) if total else 0.5,
        shots=side.shots,
        shots_on_target=side.on_target,
        xg=round(side.xg, 4),
        passes=side.passes,
        pass_accuracy=round(side.completed / side.passes, 4) if side.passes else 0.0,
        fouls=side.fouls,
        corners=side.corners,
        yellows=side.yellows,
        reds=side.reds,
    )


def _player_rows(setup: MatchSetup, tally: _Tally, minutes: int) -> tuple[PlayerMatchStats, ...]:
    rows = []
    for sheet in (setup.home, setup.away):
        for slot in sorted(sheet.lineup, key=lambda lineup_slot: lineup_slot.slot):
            counted = tally.players.get(slot.player_id, _Player())
            rows.append(
                PlayerMatchStats(
                    player_id=slot.player_id,
                    minutes=minutes,
                    goals=counted.goals,
                    assists=counted.assists,
                    shots=counted.shots,
                    xg=round(counted.xg, 4),
                    yellows=counted.yellows,
                    reds=counted.reds,
                )
            )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class SummaryInputs:
    """The identity of a run that goes into the summary beside the events."""

    seed: int
    config_hash: str
    log_digest: str


def build_summary(
    events: Sequence[MatchEvent], setup: MatchSetup, inputs: SummaryInputs
) -> MatchSummary:
    """Fold the events (everything before the summary event) into a `MatchSummary`."""
    tally = _Tally()
    for event in events:
        handler = _HANDLERS.get(type(event))
        if handler is not None:
            handler(tally, event)
    _attribute_possession(tally, events)
    duration = match_duration_s(events)
    ht_home, ht_away = halftime_score(events)
    score_home = sum(isinstance(e, GoalEvent) and e.team == "home" for e in events)
    score_away = sum(isinstance(e, GoalEvent) and e.team == "away" for e in events)
    return MatchSummary(
        config_hash=inputs.config_hash,
        seed=inputs.seed,
        log_digest=inputs.log_digest,
        score_home=score_home,
        score_away=score_away,
        ht_home=ht_home,
        ht_away=ht_away,
        attendance=setup.attendance,
        duration_s=duration,
        team_stats_home=_team_stats(tally.home, tally.away),
        team_stats_away=_team_stats(tally.away, tally.home),
        player_stats=_player_rows(setup, tally, duration // SECONDS_PER_MINUTE),
    )


def setup_ref(setup: MatchSetup) -> SetupRef:
    """Return the lightweight identity of a setup for the `MatchResult`."""
    return SetupRef(
        match_id=setup.match_id,
        home_club_id=setup.home.club.id,
        away_club_id=setup.away.club.id,
        fixture_id=setup.fixture_id,
    )
