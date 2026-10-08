"""Counting stats: one pass over the events fills a team tally per side and one per player.

Every number in `TeamStats` and `PlayerMatchStats` that is a count or a sum comes from here, so
the team totals and the player rows are guaranteed to agree (the player rows add up to the team
rows for the stats both carry). Possession and the rest of the summary are built elsewhere.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from footystreams.domain.match import MatchSetup
from footystreams.domain.types import PlayerId
from footystreams.events.clock import period_elapsed_s
from footystreams.events.derive.threat import frame_value
from footystreams.events.discipline import CardEvent, FoulEvent, SubstitutionEvent
from footystreams.events.open_play import (
    ClearanceEvent,
    DribbleEvent,
    GoalEvent,
    InterceptionEvent,
    OffsideEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.restarts import CornerEvent
from footystreams.events.types import MatchEvent

MAX_POSSESSION_INTERVAL_S = 30  # longer gaps are dead time (celebrations, treatment), not play
BIG_CHANCE_XG = 0.3
FINAL_THIRD_X = 2 / 3
ON_TARGET = ("goal", "saved")


@dataclass(slots=True)
class SideTally:
    """One side's counts."""

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
    key_passes: int = 0
    dribbles: int = 0
    dribbles_won: int = 0
    tackles: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    clearances: int = 0
    offsides: int = 0
    saves: int = 0
    big_chances: int = 0
    xt: float = 0.0
    final_third_passes: int = 0
    conceded: int = 0


@dataclass(slots=True)
class PlayerTally:
    """One player's counts."""

    goals: int = 0
    assists: int = 0
    shots: int = 0
    on_target: int = 0
    xg: float = 0.0
    xa: float = 0.0
    xt: float = 0.0
    passes: int = 0
    completed: int = 0
    key_passes: int = 0
    progressive: int = 0
    dribbles: int = 0
    dribbles_won: int = 0
    tackles: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    clearances: int = 0
    fouls: int = 0
    fouled: int = 0
    saves: int = 0
    goals_conceded: int = 0
    yellows: int = 0
    reds: int = 0


@dataclass(slots=True)
class Tally:
    """Both sides, every player, and who is in goal for each side right now."""

    home: SideTally = field(default_factory=SideTally)
    away: SideTally = field(default_factory=SideTally)
    players: dict[PlayerId, PlayerTally] = field(default_factory=dict)
    keeper: dict[str, PlayerId] = field(default_factory=dict)

    def side(self, team: str) -> SideTally | None:
        """Return the tally of a team label (None for events that belong to neither)."""
        return self.home if team == "home" else self.away if team == "away" else None

    def player(self, player_id: PlayerId) -> PlayerTally:
        """Return (creating on first use) a player's tally."""
        return self.players.setdefault(player_id, PlayerTally())


def _on_shot(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, ShotEvent)  # noqa: S101 - narrows the dispatch table's type
    side, player = tally.side(event.team), tally.player(event.player_id)
    big = event.xg >= BIG_CHANCE_XG
    on_target = event.outcome in ON_TARGET
    if side is not None:
        side.shots += 1
        side.on_target += on_target
        side.xg += event.xg
        side.big_chances += big
    player.shots += 1
    player.on_target += on_target
    player.xg += event.xg
    if event.assist_id is not None:
        passer = tally.player(event.assist_id)
        passer.key_passes += 1
        passer.xa += event.xg
        if side is not None:
            side.key_passes += 1


def _on_goal(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, GoalEvent)  # noqa: S101
    if not event.own_goal:
        tally.player(event.scorer_id).goals += 1
    if event.assist_id is not None:
        tally.player(event.assist_id).assists += 1
    conceding = "away" if event.team == "home" else "home"
    side = tally.side(conceding)
    if side is not None:
        side.conceded += 1
    keeper = tally.keeper.get(conceding)
    if keeper is not None:
        tally.player(keeper).goals_conceded += 1


def _on_pass(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, PassEvent)  # noqa: S101
    side, player = tally.side(event.team), tally.player(event.from_player_id)
    done = event.outcome == "complete"
    player.passes += 1
    player.completed += done
    if side is not None:
        side.passes += 1
        side.completed += done
    if not done:
        return
    player.xt += event.xt_gain
    player.progressive += event.progressive
    if side is not None:
        side.xt += event.xt_gain
        if event.end_pos is not None:
            reach = frame_value(event.end_pos.x, event.ctx.attack_dir)
            side.final_third_passes += reach > FINAL_THIRD_X


def _on_dribble(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, DribbleEvent)  # noqa: S101
    won = event.outcome == "success"
    tally.player(event.player_id).dribbles += 1
    tally.player(event.player_id).dribbles_won += won
    side = tally.side(event.team)
    if side is not None:
        side.dribbles += 1
        side.dribbles_won += won


def _on_tackle(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, TackleEvent)  # noqa: S101
    if event.outcome == "foul":
        return
    won = event.outcome == "won"
    tally.player(event.player_id).tackles += 1
    tally.player(event.player_id).tackles_won += won
    side = tally.side(event.team)
    if side is not None:
        side.tackles += 1
        side.tackles_won += won


def _on_interception(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, InterceptionEvent)  # noqa: S101
    tally.player(event.player_id).interceptions += 1
    side = tally.side(event.team)
    if side is not None:
        side.interceptions += 1


def _on_clearance(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, ClearanceEvent)  # noqa: S101
    tally.player(event.player_id).clearances += 1
    side = tally.side(event.team)
    if side is not None:
        side.clearances += 1


def _on_save(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, SaveEvent)  # noqa: S101
    tally.player(event.keeper_id).saves += 1
    side = tally.side(event.team)
    if side is not None:
        side.saves += 1


def _on_offside(tally: Tally, event: MatchEvent) -> None:
    side = tally.side(event.team)
    if side is not None:
        side.offsides += 1


def _on_foul(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, FoulEvent)  # noqa: S101
    tally.player(event.fouler_id).fouls += 1
    tally.player(event.fouled_id).fouled += 1
    side = tally.side(event.team)
    if side is not None:
        side.fouls += 1


def _on_corner(tally: Tally, event: MatchEvent) -> None:
    side = tally.side(event.team)
    if side is not None:
        side.corners += 1


def _on_card(tally: Tally, event: MatchEvent) -> None:
    assert isinstance(event, CardEvent)  # noqa: S101
    side, player = tally.side(event.team), tally.player(event.player_id)
    sent_off = event.colour != "yellow"
    booked = event.colour != "red"
    if side is not None:
        side.reds += sent_off
        side.yellows += booked
    player.reds += sent_off
    player.yellows += booked
    if sent_off and tally.keeper.get(event.team) == event.player_id:
        del tally.keeper[event.team]  # an outfielder takes the gloves: nobody to credit


def _on_substitution(tally: Tally, event: MatchEvent) -> None:
    """A goalkeeper's replacement takes over in goal."""
    assert isinstance(event, SubstitutionEvent)  # noqa: S101
    if tally.keeper.get(event.team) == event.player_off_id:
        tally.keeper[event.team] = event.player_on_id


_HANDLERS: dict[type, Callable[[Tally, MatchEvent], None]] = {
    ShotEvent: _on_shot,
    GoalEvent: _on_goal,
    PassEvent: _on_pass,
    DribbleEvent: _on_dribble,
    TackleEvent: _on_tackle,
    InterceptionEvent: _on_interception,
    ClearanceEvent: _on_clearance,
    SaveEvent: _on_save,
    OffsideEvent: _on_offside,
    FoulEvent: _on_foul,
    CornerEvent: _on_corner,
    CardEvent: _on_card,
    SubstitutionEvent: _on_substitution,
}


def _attribute_possession(tally: Tally, events: Sequence[MatchEvent]) -> None:
    """Credit each gap between events of one period to the side that acted at its start."""
    for current, following in pairwise(events):
        side = tally.side(current.team)
        if (
            side is None
            or isinstance(current, GoalEvent)
            or current.clock.period != following.clock.period
        ):
            continue
        gap = period_elapsed_s(following.clock) - period_elapsed_s(current.clock)
        side.possession_s += min(max(gap, 0), MAX_POSSESSION_INTERVAL_S)


def tally_events(events: Sequence[MatchEvent], setup: MatchSetup) -> Tally:
    """Fold the events into team and player counts (goalkeepers start in slot 0)."""
    tally = Tally()
    for team, sheet in (("home", setup.home), ("away", setup.away)):
        keeper = next((slot.player_id for slot in sheet.lineup if slot.slot == 0), None)
        if keeper is not None:
            tally.keeper[team] = keeper
    for event in events:
        handler = _HANDLERS.get(type(event))
        if handler is not None:
            handler(tally, event)
    _attribute_possession(tally, events)
    return tally
