from collections import Counter
from dataclasses import replace

import pytest

from footystreams.events.open_play import GoalEvent, SaveEvent, ShotEvent
from footystreams.sim.actions.resolve_shot import (
    goal_given_on_target,
    keeper_rating,
    resolve_shot,
    shot_shares,
)
from footystreams.sim.decision import team_weights
from footystreams.sim.options import ActionKind, Option, generate_options
from footystreams.sim.play import Play
from tests.factories.sim_play import make_play

XG = 0.3


def _shooting_play(seed: int) -> tuple[Play, Option]:
    play = make_play(seed)
    shooter = play.state.home.players[10]
    shooter.x, shooter.y = 0.9, 0.5
    play.state.carrier = shooter
    play.state.ball_x, play.state.ball_y = 0.9, 0.5
    play.state.assist_from = play.state.home.players[8]
    keeper = play.state.away.keeper
    keeper.skills = replace(keeper.skills, shot_stopping=55.0, handling=55.0, positioning=55.0)
    options = generate_options(play.state, 0.0, team_weights(play.state, play.cfg), play.cfg)
    option = next(item for item in options if item.kind is ActionKind.SHOOT)
    return play, replace(option, xg=XG)


def test_resolve_shot__over_many_shots_goal_rate_matches_the_xg() -> None:
    goals = 0
    trials = 1500
    for seed in range(trials):
        play, option = _shooting_play(seed)
        resolve_shot(play, option)
        goals += any(isinstance(event, GoalEvent) for event in play.emit.events)
    assert abs(goals / trials - XG) < 0.04


def test_resolve_shot__every_outcome_is_reachable() -> None:
    outcomes: Counter[str] = Counter()
    for seed in range(400):
        play, option = _shooting_play(seed)
        resolve_shot(play, option)
        outcomes[next(e for e in play.emit.events if isinstance(e, ShotEvent)).outcome] += 1
    assert set(outcomes) == {"goal", "saved", "blocked", "off_target", "woodwork"}


def test_resolve_shot__goal_follows_the_shot_updates_score_and_restarts_from_the_centre() -> None:
    for seed in range(200):
        play, option = _shooting_play(seed)
        duration = resolve_shot(play, option)
        shot, *rest = play.emit.events
        if isinstance(shot, ShotEvent) and shot.outcome == "goal":
            goal = rest[0]
            assert isinstance(goal, GoalEvent)
            assert goal.caused_by == shot.id
            assert goal.shot_event_id == shot.id
            assert goal.assist_id == play.state.home.players[8].player_id
            assert goal.ctx.score_home == 1
            assert play.state.home.score == 1
            assert play.state.carrier.side == "away"
            assert (play.state.ball_x, play.state.ball_y) == (0.5, 0.5)
            assert duration > 30.0
            return
    pytest.fail("no goal in 200 seeds")


def test_resolve_shot__save_follows_the_shot_with_the_keeper_and_shot_id() -> None:
    for seed in range(200):
        play, option = _shooting_play(seed)
        resolve_shot(play, option)
        shot, *rest = play.emit.events
        if isinstance(shot, ShotEvent) and shot.outcome == "saved":
            save = rest[0]
            assert isinstance(save, SaveEvent)
            assert save.shot_event_id == shot.id
            assert save.keeper_id == play.state.away.keeper.player_id
            return
    pytest.fail("no save in 200 seeds")


def test_resolve_shot__assist_is_only_the_last_passer_in_the_chain() -> None:
    play, option = _shooting_play(1)
    play.state.assist_from = None
    resolve_shot(play, option)
    shot = next(e for e in play.emit.events if isinstance(e, ShotEvent))
    assert shot.assist_id is None


def test_shot_shares__are_ordered_and_a_better_finisher_misses_less() -> None:
    play = make_play()
    weak = shot_shares(play, 0.0, 30.0)
    strong = shot_shares(play, 0.0, 90.0)
    assert 0.0 < weak.blocked < weak.off_target < weak.woodwork < 1.0
    assert strong.off_target - strong.blocked < weak.off_target - weak.blocked


def test_goal_given_on_target__better_keepers_concede_less() -> None:
    play = make_play()
    shares = shot_shares(play, 0.0, 50.0)
    keeper = play.state.away.keeper
    weak = replace(keeper, skills=replace(keeper.skills, shot_stopping=10.0))
    strong = replace(keeper, skills=replace(keeper.skills, shot_stopping=95.0))
    assert goal_given_on_target(play, XG, shares, strong) < goal_given_on_target(
        play, XG, shares, weak
    )
    assert keeper_rating(strong) > keeper_rating(weak)
