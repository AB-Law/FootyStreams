"""Resolve a dribble and a clearance."""

from __future__ import annotations

from footystreams.events.open_play import ClearanceEvent, DribbleEvent, TackleEvent
from footystreams.sim.actions.challenge import closest_of, nearest_defender_to
from footystreams.sim.actions.foul import contest_foul
from footystreams.sim.actions.out_of_play import out_of_play
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import CENTRE
from footystreams.sim.options import Option
from footystreams.sim.play import Play, action_duration, actor, take_possession
from footystreams.sim.pressure import nearest_opponents
from footystreams.sim.state import PlayerState

TOUCH_MARGIN = 0.01  # how far beyond the line a ball that went out is placed


def resolve_dribble(play: Play, option: Option) -> float:
    """Play out the dribble: carry the ball on, or lose it to a tackle or a heavy touch."""
    state = play.state
    carrier = state.carrier
    start = (carrier.x, carrier.y)
    beaten = play.rng.u() < option.probability
    if beaten:
        outcome = "success"
    else:
        tackled = play.rng.u() < play.cfg.challenge.dribble_tackled_share
        outcome = "tackled" if tackled else "lost"
    meta = Meta(team=carrier.side, participants=(actor(carrier, "carrier"),), pos=start)
    dribble_id = play.emit.emit(
        state, DribbleEvent, meta, player_id=carrier.player_id, outcome=outcome
    )
    duration = action_duration(play, play.cfg.tempo.dribble_s)
    if beaten:
        carrier.x, carrier.y = option.end
        state.ball_x, state.ball_y = option.end
        state.assist_from = None
        return duration
    return duration + _lose_dribble(play, start, dribble_id, tackled=outcome == "tackled")


def _lose_dribble(
    play: Play, start: tuple[float, float], dribble_id: str, *, tackled: bool
) -> float:
    """Lose the ball to a tackle or a heavy touch; return any extra stoppage (a called foul)."""
    state = play.state
    carrier = state.carrier
    defender = nearest_opponents(state.defenders, start[0], start[1], 1)[0][1]
    if tackled:
        stoppage = contest_foul(play, defender, carrier, dribble_id)
        if stoppage is not None:
            return stoppage
        meta = Meta(
            team=defender.side,
            participants=(actor(defender, "tackler"), actor(carrier, "carrier")),
            pos=start,
            caused_by=dribble_id,
        )
        play.emit.emit(
            state,
            TackleEvent,
            meta,
            player_id=defender.player_id,
            target_id=carrier.player_id,
            outcome="won",
        )
    cfg = play.cfg.restarts
    if not tackled and cfg.enabled and play.setpiece.u() < cfg.dribble_out_share:
        return out_of_play(play, _into_touch(start), carrier.side)
    take_possession(state, defender, start[0], start[1])
    return 0.0


def resolve_clearance(play: Play, option: Option) -> float:
    """Hoof the ball clear: it lands near the option's end and the nearest man there wins it.

    With restarts enabled a share of clearances go into touch instead (a throw-in).
    """
    state, cfg = play.state, play.cfg.challenge
    clearer = state.carrier
    spread = cfg.clearance_spread * play.rng.gauss()
    landing = (option.end[0], min(1.0, max(0.0, option.end[1] + spread)))
    teammate_wins = play.rng.u() < cfg.clearance_teammate_share
    meta = Meta(
        team=clearer.side, participants=(actor(clearer, "actor"),), pos=(clearer.x, clearer.y)
    )
    play.emit.emit(state, ClearanceEvent, meta, player_id=clearer.player_id)
    duration = action_duration(play, play.cfg.tempo.clear_s)
    if play.cfg.restarts.enabled and play.rng.u() < play.cfg.restarts.clearance_out_share:
        return duration + out_of_play(play, _into_touch(landing), clearer.side)
    winner = _clearance_winner(play, clearer, landing, teammate_wins=teammate_wins)
    take_possession(state, winner, landing[0], landing[1])
    return duration


def _into_touch(landing: tuple[float, float]) -> tuple[float, float]:
    """Return a point just beyond the touchline nearest to where a clearance landed."""
    return landing[0], -TOUCH_MARGIN if landing[1] < CENTRE else 1.0 + TOUCH_MARGIN


def _clearance_winner(
    play: Play, clearer: PlayerState, landing: tuple[float, float], *, teammate_wins: bool
) -> PlayerState:
    if teammate_wins:
        mates = [player for player in play.state.attackers.players if player is not clearer]
        return closest_of(mates, landing)
    return nearest_defender_to(play, landing)
