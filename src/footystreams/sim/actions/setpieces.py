"""Helpers shared by the dead-ball restarts: stoppage lengths and the free-kick taker.

Delays are drawn from the `setpiece` stream.
"""

from __future__ import annotations

from footystreams.sim.play import Play
from footystreams.sim.state import PlayerState, TeamState


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
