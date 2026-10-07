"""Resolve a shot: blocked, off target, woodwork, saved or scored, and the restart after a goal.

Outcome shares are built so that, averaged over keepers, the chance of a goal equals the shot's
xG: the on-target share is whatever remains after blocks, misses and woodwork, and the keeper
turns `xg / on_target` into a save or a goal (docs/design/02 section 5.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.events.open_play import GoalEvent, SaveEvent, ShotEvent
from footystreams.sim.actions.challenge import closest_of
from footystreams.sim.actions.out_of_play import out_of_play
from footystreams.sim.actions.shooting import finishing_skill
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import frame_coordinate, goal_distance_m
from footystreams.sim.mathx import clamp
from footystreams.sim.options import Option
from footystreams.sim.play import Play, action_duration, actor, label, take_possession
from footystreams.sim.positioning import place_for_kickoff
from footystreams.sim.pressure import nearest_opponents
from footystreams.sim.side import Side, opposite
from footystreams.sim.state import PlayerState

_PERCENT = 100.0
_SKILL_PIVOT = 50.0
_KEEPER_PIVOT = 55.0
_KEEPER_MIX = (0.6, 0.2, 0.2)  # shot stopping, handling, positioning
_KEEPER_RELEASE_FRAME_X = 0.06  # where a keeper stands after collecting the ball
_HOLD_NEAREST = 1


@dataclass(frozen=True, slots=True)
class ShotShares:
    """Cumulative outcome thresholds for one shot (blocked, off target, woodwork, on target)."""

    blocked: float
    off_target: float
    woodwork: float


def keeper_rating(keeper: PlayerState) -> float:
    """Blend of the attributes that stop a shot (1-100 scale)."""
    a, b, c = _KEEPER_MIX
    skills = keeper.skills
    return a * skills.shot_stopping + b * skills.handling + c * skills.positioning


def shot_shares(play: Play, pressure: float, shooter_skill: float) -> ShotShares:
    """Return cumulative thresholds for blocked, off target and woodwork; the rest is on target."""
    cfg = play.cfg.shot
    blocked = cfg.block_base + cfg.block_pressure * pressure
    skill_edge = (shooter_skill - _SKILL_PIVOT) / _SKILL_PIVOT
    off_target = cfg.off_target_base - cfg.off_target_skill_swing * skill_edge
    off_target = clamp(off_target, 0.05, 0.6)
    on_frame = 1.0 - blocked - off_target
    woodwork = cfg.woodwork_share * on_frame
    return ShotShares(blocked, blocked + off_target, blocked + off_target + woodwork)


def goal_given_on_target(play: Play, xg: float, shares: ShotShares, keeper: PlayerState) -> float:
    """Return the chance an on-target shot beats this keeper (xG divided by the on-target share)."""
    on_target = 1.0 - shares.woodwork
    keeper_factor = (
        1.0 - play.cfg.shot.keeper_swing * (keeper_rating(keeper) - _KEEPER_PIVOT) / _PERCENT
    )
    return clamp(xg / on_target * keeper_factor, 0.0, play.cfg.shot.max_goal_given_on_target)


def _assist_id(play: Play, shooter: PlayerState) -> str | None:
    passer = play.state.assist_from
    return passer.player_id if passer is not None and passer is not shooter else None


def resolve_shot(play: Play, option: Option) -> float:
    """Play out the shot and return the seconds it took (long after a goal: celebration)."""
    state = play.state
    shooter, keeper = state.carrier, state.defenders.keeper
    direction = state.attackers.attack_dir
    distance = goal_distance_m(
        frame_coordinate(shooter.x, direction), frame_coordinate(shooter.y, direction)
    )
    skill = finishing_skill(shooter.skills, distance, play.cfg.shot)
    shares = shot_shares(play, option.pressure, skill)
    roll = play.rng.u()
    if roll < shares.blocked:
        outcome = "blocked"
    elif roll < shares.off_target:
        outcome = "off_target"
    elif roll < shares.woodwork:
        outcome = "woodwork"
    else:
        scored = play.rng.u() < goal_given_on_target(play, option.xg, shares, keeper)
        outcome = "goal" if scored else "saved"
    assist = _assist_id(play, shooter)
    meta = Meta(
        team=shooter.side,
        participants=(actor(shooter, "shooter"),),
        pos=(shooter.x, shooter.y),
        headline=f"{label(state.attackers, shooter.player_id)} shoots",
    )
    shot_id = play.emit.emit(
        state,
        ShotEvent,
        meta,
        player_id=shooter.player_id,
        xg=round(option.xg, 4),
        outcome=outcome,
        assist_id=assist,
    )
    return _after_shot(play, outcome, shot_id, assist) + action_duration(
        play, play.cfg.tempo.shot_s
    )


def _after_shot(play: Play, outcome: str, shot_id: str, assist: str | None) -> float:
    """Apply the consequences of a shot outcome; return extra seconds (goal, restarts)."""
    state = play.state
    if outcome == "goal":
        return _score_goal(play, shot_id, assist)
    if outcome == "saved":
        return _record_save(play, shot_id)
    if outcome == "off_target":
        return _behind(play, last_touch=state.carrier.side, keeper_collects=True)
    if outcome == "blocked" and _deflected_behind(play, play.cfg.restarts.blocked_corner_share):
        return _behind(play, last_touch=state.defenders.side, keeper_collects=False)
    _loose_ball(play, (state.ball_x, state.ball_y))
    return 0.0


def _deflected_behind(play: Play, share: float) -> bool:
    """True when restarts are on and the ball runs out behind the goal (one `setpiece` draw)."""
    return play.cfg.restarts.enabled and play.setpiece.u() < share


def _behind(play: Play, *, last_touch: Side, keeper_collects: bool) -> float:
    """The ball goes out behind the goal: a goal kick or corner, or the keeper just collects it."""
    state = play.state
    if not play.cfg.restarts.enabled:
        if keeper_collects:
            _keeper_collects(play)
        return 0.0
    goal_x = frame_coordinate(1.0, state.attackers.attack_dir)
    return out_of_play(play, (goal_x, state.carrier.y), last_touch)


def _keeper_collects(play: Play) -> None:
    state = play.state
    keeper = state.defenders.keeper
    spot_x = frame_coordinate(_KEEPER_RELEASE_FRAME_X, state.defenders.attack_dir)
    take_possession(state, keeper, spot_x, keeper.y)


def _record_save(play: Play, shot_id: str) -> float:
    state = play.state
    shooter, keeper = state.carrier, state.defenders.keeper
    meta = Meta(
        team=keeper.side,
        participants=(actor(keeper, "keeper"), actor(shooter, "shooter")),
        pos=(keeper.x, keeper.y),
        caused_by=shot_id,
        headline=f"{label(state.defenders, keeper.player_id)} saves",
    )
    play.emit.emit(state, SaveEvent, meta, keeper_id=keeper.player_id, shot_event_id=shot_id)
    if play.rng.u() < play.cfg.shot.keeper_holds:
        _keeper_collects(play)
    elif _deflected_behind(play, play.cfg.restarts.parry_corner_share):
        return _behind(play, last_touch=keeper.side, keeper_collects=False)
    else:
        _loose_ball(play, (keeper.x, keeper.y))
    return 0.0


def _loose_ball(play: Play, spot: tuple[float, float]) -> None:
    """A parried or blocked ball: the nearest attacker or defender gets there first."""
    state = play.state
    attacker_first = play.rng.u() < play.cfg.shot.rebound_attacker_share
    if attacker_first:
        others = [player for player in state.attackers.players if player is not state.carrier]
        winner = closest_of(others, spot)
    else:
        winner = nearest_opponents(state.defenders, spot[0], spot[1], _HOLD_NEAREST)[0][1]
    take_possession(state, winner, spot[0], spot[1])


def _score_goal(play: Play, shot_id: str, assist: str | None) -> float:
    state = play.state
    scorer = state.carrier
    state.attackers.score += 1
    meta = Meta(
        team=scorer.side,
        participants=(actor(scorer, "scorer"),),
        pos=(scorer.x, scorer.y),
        caused_by=shot_id,
        headline=f"GOAL {label(state.attackers, scorer.player_id)}",
    )
    play.emit.emit(
        state,
        GoalEvent,
        meta,
        scorer_id=scorer.player_id,
        assist_id=assist,
        shot_event_id=shot_id,
    )
    place_for_kickoff(state, opposite(scorer.side))
    state.chain += 1
    state.chain_started_at = state.elapsed_s
    state.assist_from = None
    tempo = play.cfg.tempo
    return tempo.celebration_s + tempo.celebration_spread_s * (play.rng.u() - 0.5) * 2.0
