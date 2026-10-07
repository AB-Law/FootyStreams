"""Resolve a dribble and a clearance."""

from __future__ import annotations

from footystreams.events.open_play import ClearanceEvent, DribbleEvent, TackleEvent
from footystreams.sim.actions.challenge import closest_of, nearest_defender_to
from footystreams.sim.emit import Meta
from footystreams.sim.options import Option
from footystreams.sim.play import Play, action_duration, actor, take_possession
from footystreams.sim.pressure import nearest_opponents
from footystreams.sim.state import PlayerState


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
    if beaten:
        carrier.x, carrier.y = option.end
        state.ball_x, state.ball_y = option.end
        state.assist_from = None
    else:
        _lose_dribble(play, start, dribble_id, tackled=outcome == "tackled")
    return action_duration(play, play.cfg.tempo.dribble_s)


def _lose_dribble(
    play: Play, start: tuple[float, float], dribble_id: str, *, tackled: bool
) -> None:
    state = play.state
    carrier = state.carrier
    defender = nearest_opponents(state.defenders, start[0], start[1], 1)[0][1]
    if tackled:
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
    take_possession(state, defender, start[0], start[1])


def resolve_clearance(play: Play, option: Option) -> float:
    """Hoof the ball clear: it lands near the option's end and the nearest man there wins it."""
    state, cfg = play.state, play.cfg.challenge
    clearer = state.carrier
    spread = cfg.clearance_spread * play.rng.gauss()
    landing = (option.end[0], min(1.0, max(0.0, option.end[1] + spread)))
    teammate_wins = play.rng.u() < cfg.clearance_teammate_share
    meta = Meta(
        team=clearer.side, participants=(actor(clearer, "actor"),), pos=(clearer.x, clearer.y)
    )
    play.emit.emit(state, ClearanceEvent, meta, player_id=clearer.player_id)
    winner = _clearance_winner(play, clearer, landing, teammate_wins=teammate_wins)
    take_possession(state, winner, landing[0], landing[1])
    return action_duration(play, play.cfg.tempo.clear_s)


def _clearance_winner(
    play: Play, clearer: PlayerState, landing: tuple[float, float], *, teammate_wins: bool
) -> PlayerState:
    if teammate_wins:
        mates = [player for player in play.state.attackers.players if player is not clearer]
        return closest_of(mates, landing)
    return nearest_defender_to(play, landing)
