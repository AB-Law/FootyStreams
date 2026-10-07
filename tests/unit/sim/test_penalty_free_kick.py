from collections import Counter
from dataclasses import replace

import pytest

from footystreams.events.discipline import FoulEvent
from footystreams.events.open_play import (
    ClearanceEvent,
    GoalEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.restarts import FreeKickEvent, GoalKickEvent, PenaltyEvent
from footystreams.sim.actions.foul import contest_foul
from footystreams.sim.actions.free_kick import dead_ball_skill, free_kick_xg, take_free_kick
from footystreams.sim.actions.penalty import (
    choose_penalty_taker,
    penalty_outcome,
    take_penalty,
    taker_skill,
)
from footystreams.sim.config import SimConfig, merge_config
from tests.factories.referee import make_referee
from tests.factories.sim_play import make_play

ON = merge_config(SimConfig(), {"restarts": {"enabled": True}})


def test_choose_penalty_taker__named_first_then_the_best_taker() -> None:
    play = make_play(config=ON)
    team = play.state.home
    named = team.sheet.penalty_takers[0]
    assert choose_penalty_taker(team).player_id == named
    team.players = [p for p in team.players if p.player_id != named]
    best = max(
        (p for p in team.players if p is not team.keeper), key=lambda p: (taker_skill(p), -p.slot)
    )
    assert choose_penalty_taker(team) is best


def test_penalty_outcome__conversion_for_average_players_is_in_the_realistic_band() -> None:
    results: Counter[str] = Counter()
    for seed in range(1500):
        play = make_play(seed, config=ON)
        taker, keeper = play.state.home.players[9], play.state.away.keeper
        keeper.skills = replace(
            keeper.skills, one_on_ones=55.0, shot_stopping=55.0, handling=55.0, positioning=55.0
        )
        taker.skills = replace(taker.skills, penalty_taking=55.0, composure=55.0)
        results[penalty_outcome(play, taker, keeper)] += 1
    assert 0.72 < results["goal"] / 1500 < 0.82
    assert set(results) == {"goal", "saved", "missed", "woodwork"}


def test_penalty_outcome__a_better_taker_scores_more() -> None:
    def goals(skill: float) -> int:
        total = 0
        for seed in range(600):
            play = make_play(seed, config=ON)
            taker, keeper = play.state.home.players[9], play.state.away.keeper
            taker.skills = replace(taker.skills, penalty_taking=skill, composure=skill)
            total += penalty_outcome(play, taker, keeper) == "goal"
        return total

    assert goals(90.0) > goals(20.0)


def test_take_penalty__goal_follows_the_penalty_at_the_same_moment_and_restarts() -> None:
    for seed in range(100):
        play = make_play(seed, config=ON)
        seconds = take_penalty(play, "home", "mch_demo0001:00007")
        first, *rest = play.emit.events
        assert isinstance(first, PenaltyEvent)
        assert first.caused_by == "mch_demo0001:00007"
        if first.outcome == "goal":
            goal = rest[0]
            assert isinstance(goal, GoalEvent)
            assert goal.caused_by == first.id
            assert goal.shot_event_id == first.id
            assert play.state.home.score == 1
            assert play.state.carrier.side == "away"
            assert seconds > 30.0
            return
    pytest.fail("no scored penalty")


def test_take_penalty__every_outcome_has_its_consequence() -> None:
    seen: set[str] = set()
    for seed in range(300):
        play = make_play(seed, config=ON)
        take_penalty(play, "away", "x")
        penalty = play.emit.events[0]
        assert isinstance(penalty, PenaltyEvent)
        seen.add(penalty.outcome)
        if penalty.outcome == "saved":
            save = play.emit.events[1]
            assert isinstance(save, SaveEvent)
            assert save.shot_event_id == penalty.id
        if penalty.outcome == "missed":
            assert isinstance(play.emit.events[1], GoalKickEvent)
        if penalty.outcome != "goal":
            assert play.state.away.score == 0
    assert seen == {"goal", "saved", "missed", "woodwork"}


def test_free_kick_xg__better_dead_ball_takers_and_closer_spots_are_more_dangerous() -> None:
    play = make_play(config=ON)
    taker = play.state.home.players[5]
    skilled = replace(taker, skills=replace(taker.skills, set_piece_delivery=95.0, long_shots=95.0))
    assert free_kick_xg(play, skilled, (0.85, 0.5)) > free_kick_xg(play, taker, (0.85, 0.5))
    assert free_kick_xg(play, taker, (0.9, 0.5)) > free_kick_xg(play, taker, (0.75, 0.5))
    assert dead_ball_skill(skilled) > dead_ball_skill(taker)


def test_take_free_kick__with_restarts_off_it_is_only_the_kick() -> None:
    play = make_play()
    take_free_kick(play, "home", (0.88, 0.5), "direct", None)
    assert [type(e) for e in play.emit.events] == [FreeKickEvent]


def test_take_free_kick__indirect_kicks_are_never_shot() -> None:
    cfg = merge_config(SimConfig(), {"restarts": {"enabled": True, "direct_share": 1.0}})
    play = make_play(config=cfg)
    take_free_kick(play, "home", (0.88, 0.5), "indirect", None)
    assert [type(e) for e in play.emit.events] == [FreeKickEvent]


def test_take_free_kick__direct_kick_in_range_is_shot_when_the_share_says_so() -> None:
    cfg = merge_config(SimConfig(), {"restarts": {"enabled": True, "direct_share": 1.0}})
    play = make_play(config=cfg)
    take_free_kick(play, "home", (0.88, 0.5), "direct", "mch_demo0001:00003")
    kinds = [type(e) for e in play.emit.events]
    assert kinds[0] is FreeKickEvent
    assert ShotEvent in kinds


def test_take_free_kick__long_kicks_in_the_attacking_half_are_crossed() -> None:
    cfg = merge_config(SimConfig(), {"restarts": {"enabled": True, "free_kick_cross_share": 1.0}})
    crossed: Counter[str] = Counter()
    for seed in range(60):
        play = make_play(seed, config=cfg)
        take_free_kick(play, "home", (0.66, 0.2), "direct", None)
        kinds = {type(e) for e in play.emit.events}
        crossed[
            "header" if ShotEvent in kinds else "cleared" if ClearanceEvent in kinds else "claimed"
        ] += 1
    assert set(crossed) == {"header", "cleared", "claimed"}


def test_take_free_kick__deep_in_the_own_half_the_taker_just_plays_on() -> None:
    play = make_play(config=ON)
    take_free_kick(play, "home", (0.3, 0.5), "direct", None)
    assert [type(e) for e in play.emit.events] == [FreeKickEvent]


def test_contest_foul__in_the_box_with_restarts_on_gives_a_penalty() -> None:
    cfg = merge_config(
        SimConfig(),
        {
            "discipline": {"contact_base": 1000.0, "advantage_scale": 0.0},
            "restarts": {"enabled": True},
        },
    )
    for seed in range(100):
        play = make_play(seed, config=cfg, referee=make_referee(strictness=1.0))
        carrier = play.state.carrier
        carrier.x, carrier.y = 0.94, 0.5
        play.state.ball_x, play.state.ball_y = 0.94, 0.5
        tackler = play.state.away.players[3]
        tackler.x, tackler.y = 0.95, 0.5
        if contest_foul(play, tackler, carrier, None) is None:
            continue
        kinds = [type(e) for e in play.emit.events]
        assert kinds[:2] == [TackleEvent, FoulEvent]
        assert PenaltyEvent in kinds
        assert FreeKickEvent not in kinds
        return
    pytest.fail("no foul called in the box")
