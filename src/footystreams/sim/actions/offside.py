"""Offside: the line, whether a receiver is beyond it, whether the referee flags it.

A player is in an offside position when he is nearer the opponents' goal than both the ball and
the second-last opponent (the keeper counts). An offside pass that the referee spots is an
`offside` event followed by an indirect free kick for the defenders; a missed flag lets play go on
(docs/design/02 section 5.3). The call is a `discipline` draw.
"""

from __future__ import annotations

from footystreams.events.open_play import OffsideEvent
from footystreams.sim.actions.free_kick import take_free_kick
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import frame_coordinate
from footystreams.sim.mathx import PERCENT
from footystreams.sim.offside import call_probability, in_offside_position, offside_line
from footystreams.sim.play import Play, actor
from footystreams.sim.side import opposite
from footystreams.sim.state import PlayerState


def offside_called(
    play: Play, passer: PlayerState, receiver: PlayerState, *, runs_in_behind: bool = True
) -> bool:
    """Decide if a pass to `receiver` is flagged (no draw unless he is on or near the line).

    Only a ball played in behind (`runs_in_behind`) can catch a runner who set off early.
    """
    state = play.state
    direction = state.team(passer.side).attack_dir
    line = offside_line(state.team(opposite(passer.side)), direction)
    ahead = frame_coordinate(receiver.x, direction)
    if not in_offside_position(ahead, frame_coordinate(passer.x, direction), line):
        return runs_in_behind and _mistimed_run(play, receiver, ahead, line) and _flagged(play)
    return _flagged(play)


def _flagged(play: Play) -> bool:
    """The referee spots it (one `discipline` draw)."""
    return play.discipline.u() < call_probability(play.referee.consistency, play.cfg.offside)


def _mistimed_run(play: Play, receiver: PlayerState, ahead: float, line: float) -> bool:
    """A receiver level with the line may have set off a stride early (one draw near the line)."""
    cfg = play.cfg.offside
    if cfg.mistime_base <= 0.0 or ahead < line - cfg.mistime_zone:
        return False
    flaw = cfg.mistime_base * (1.3 - receiver.skills.off_ball_movement / PERCENT)
    return play.discipline.u() < flaw


def punish_offside(play: Play, receiver: PlayerState, pass_id: str) -> float:
    """Emit the offside and restart with an indirect free kick; return the stoppage seconds."""
    state = play.state
    spot = (receiver.x, receiver.y)
    meta = Meta(
        team=receiver.side,
        participants=(actor(receiver, "offside_player"),),
        pos=spot,
        caused_by=pass_id,
    )
    offside_id = play.emit.emit(state, OffsideEvent, meta, player_id=receiver.player_id)
    return take_free_kick(play, opposite(receiver.side), spot, "indirect", offside_id)
