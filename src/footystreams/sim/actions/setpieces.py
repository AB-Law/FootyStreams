"""Dead-ball restarts taken by a named player: free kicks (and, later, throw-ins and corners).

Each restart emits its event, gives the ball to the taker at the spot and returns the seconds the
stoppage lasts. Delays are drawn from the `setpiece` stream.
"""

from __future__ import annotations

from typing import Literal

from footystreams.events.restarts import FreeKickEvent
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import Point
from footystreams.sim.play import Play, actor, take_possession
from footystreams.sim.side import Side
from footystreams.sim.state import PlayerState, TeamState

FreeKickKind = Literal["direct", "indirect"]


def restart_delay(play: Play, centre_s: float, spread_s: float) -> float:
    """Return a stoppage length of `centre_s +- spread_s` seconds (one `setpiece` draw)."""
    return centre_s + spread_s * (play.setpiece.u() - 0.5) * 2.0


def choose_free_kick_taker(team: TeamState) -> PlayerState:
    """Pick the named taker still on the pitch, else the best deliverer of the ball."""
    for player_id in team.sheet.free_kick_takers:
        for player in team.players:
            if player.player_id == player_id:
                return player
    outfield = [player for player in team.players if player is not team.keeper]
    return max(outfield, key=lambda player: (player.skills.set_piece_delivery, -player.slot))


def take_free_kick(
    play: Play, side: Side, spot: Point, kind: FreeKickKind, caused_by: str | None
) -> float:
    """Restart play with a free kick for `side` at `spot`; return the stoppage in seconds."""
    state = play.state
    taker = choose_free_kick_taker(state.team(side))
    meta = Meta(team=side, participants=(actor(taker, "taker"),), pos=spot, caused_by=caused_by)
    play.emit.emit(state, FreeKickEvent, meta, taker_id=taker.player_id, kind=kind)
    take_possession(state, taker, spot[0], spot[1])
    cfg = play.cfg.discipline
    return restart_delay(play, cfg.free_kick_s, cfg.free_kick_spread_s)
