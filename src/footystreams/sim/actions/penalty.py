"""Penalties: the taker, the keeper's duel and the consequence (docs/design/02 section 6).

A penalty is its own event (`penalty`) carrying the outcome; a scored one is followed by a `goal`
at the same moment, a saved one by a `save` caused by the penalty. Draws come from `setpiece`.
"""

from __future__ import annotations

from footystreams.events.open_play import SaveEvent
from footystreams.events.restarts import PenaltyEvent
from footystreams.sim.actions.out_of_play import out_of_play
from footystreams.sim.actions.resolve_shot import after_save, keeper_rating, loose_ball, score_goal
from footystreams.sim.actions.setpieces import restart_delay
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import CENTRE, PITCH_LENGTH_M, frame_coordinate
from footystreams.sim.mathx import clamp
from footystreams.sim.play import Play, actor, label, take_possession
from footystreams.sim.setpiece_shape import penalty_layout, settle
from footystreams.sim.side import Side, opposite
from footystreams.sim.state import PlayerState, TeamState

_SKILL_MIX = (0.6, 0.4)  # penalty taking, composure
_KEEPER_PIVOT = 55.0
_MIN_GOAL_GIVEN_FRAME = 0.55
_MAX_GOAL_GIVEN_FRAME = 0.92
_MISS_SKILL_SWING = 0.0012  # fewer misses per point of taker skill


def choose_penalty_taker(team: TeamState) -> PlayerState:
    """Pick the named taker still on the pitch, else the best penalty taker."""
    for player_id in team.sheet.penalty_takers:
        for player in team.players:
            if player.player_id == player_id:
                return player
    outfield = [player for player in team.players if player is not team.keeper]
    return max(outfield, key=lambda player: (taker_skill(player), -player.slot))


def taker_skill(taker: PlayerState) -> float:
    """Blend of the attributes that decide a penalty (1-100 scale)."""
    penalty, composure = _SKILL_MIX
    return penalty * taker.skills.penalty_taking + composure * taker.skills.composure


def penalty_outcome(play: Play, taker: PlayerState, keeper: PlayerState) -> str:
    """Decide goal, saved, missed or woodwork with two `setpiece` draws."""
    cfg = play.cfg.restarts
    skill = taker_skill(taker)
    edge = skill - cfg.penalty_skill_pivot
    off = clamp(cfg.penalty_off_target - _MISS_SKILL_SWING * edge, 0.02, 0.25)
    roll = play.setpiece.u()
    if roll < off:
        return "missed"
    if roll < off + cfg.penalty_woodwork:
        return "woodwork"
    beats_keeper = cfg.penalty_goal_given_frame + cfg.penalty_skill_swing * (
        edge - (keeper_rating(keeper) - _KEEPER_PIVOT)
    )
    chance = clamp(beats_keeper, _MIN_GOAL_GIVEN_FRAME, _MAX_GOAL_GIVEN_FRAME)
    return "goal" if play.setpiece.u() < chance else "saved"


def take_penalty(play: Play, side: Side, foul_id: str) -> float:
    """Take a penalty for `side`; return the stoppage seconds (the goal restart included)."""
    state, cfg = play.state, play.cfg.restarts
    team, defenders = state.team(side), state.team(opposite(side))
    taker, keeper = choose_penalty_taker(team), defenders.keeper
    spot = (
        frame_coordinate(1.0 - cfg.penalty_distance_m / PITCH_LENGTH_M, team.attack_dir),
        frame_coordinate(CENTRE, team.attack_dir),
    )
    take_possession(state, taker, spot[0], spot[1])
    outcome = penalty_outcome(play, taker, keeper)
    meta = Meta(
        team=side,
        participants=(actor(taker, "taker"), actor(keeper, "keeper")),
        pos=spot,
        caused_by=foul_id,
        headline=f"Penalty: {label(team, taker.player_id)}",
    )
    penalty_id = play.emit.emit(
        state, PenaltyEvent, meta, taker_id=taker.player_id, outcome=outcome
    )
    seconds = restart_delay(play, play.cfg.discipline.free_kick_s * 0.5, 5.0)
    settle(play, team, penalty_layout(state, team, taker), seconds, keyframe=True)
    if outcome == "goal":
        return seconds + score_goal(play, penalty_id, None)
    if outcome == "saved":
        save = Meta(
            team=keeper.side,
            participants=(actor(keeper, "keeper"), actor(taker, "shooter")),
            pos=(keeper.x, keeper.y),
            caused_by=penalty_id,
            headline=f"{label(defenders, keeper.player_id)} saves the penalty",
        )
        play.emit.emit(state, SaveEvent, save, keeper_id=keeper.player_id, shot_event_id=penalty_id)
        return seconds + after_save(play)
    if outcome == "missed":
        goal_x = frame_coordinate(1.0, team.attack_dir)
        return seconds + out_of_play(play, (goal_x, taker.y), side)
    loose_ball(play, spot)
    return seconds
