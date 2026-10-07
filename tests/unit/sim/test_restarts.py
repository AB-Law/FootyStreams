from collections import Counter
from dataclasses import replace

import pytest

from footystreams.events.open_play import ClearanceEvent, PassEvent, ShotEvent
from footystreams.events.restarts import CornerEvent, GoalKickEvent, ThrowInEvent
from footystreams.sim.actions.corner import (
    attacking_strength,
    build_duel,
    choose_corner_taker,
    corner,
    defending_strength,
    header_xg,
)
from footystreams.sim.actions.out_of_play import defending_side_of_goal, out_of_play
from footystreams.sim.actions.resolve_dribble import resolve_clearance, resolve_dribble
from footystreams.sim.actions.resolve_pass import resolve_pass
from footystreams.sim.actions.restarts import (
    goal_kick,
    left_pitch,
    nearest_outfielder,
    overhit_point,
    throw_in,
)
from footystreams.sim.config import SimConfig, merge_config
from footystreams.sim.decision import team_weights
from footystreams.sim.options import ActionKind, Option, generate_options
from footystreams.sim.play import Play
from tests.factories.sim_play import make_play

ENABLED = merge_config(SimConfig(), {"restarts": {"enabled": True}})


def _play(seed: int = 1) -> Play:
    return make_play(seed, config=ENABLED)


def test_left_pitch__inside_and_outside_points() -> None:
    assert not left_pitch((0.5, 0.5))
    assert not left_pitch((0.0, 1.0))
    assert left_pitch((1.01, 0.5))
    assert left_pitch((0.5, -0.01))


def test_overhit_point__extends_the_pass_direction_by_the_requested_metres() -> None:
    landing = overhit_point((0.5, 0.5), (0.6, 0.5), 10.5)
    assert landing[0] == pytest.approx(0.7)
    assert landing[1] == pytest.approx(0.5)


def test_overhit_point__zero_length_pass_stays_put() -> None:
    assert overhit_point((0.5, 0.5), (0.5, 0.5), 5.0) == (0.5, 0.5)


def test_nearest_outfielder__never_the_goalkeeper() -> None:
    play = _play()
    team = play.state.home
    assert nearest_outfielder(team, (0.0, 0.5)) is not team.keeper


def test_throw_in__nearest_outfielder_takes_it_and_the_team_gets_the_ball() -> None:
    play = _play()
    seconds = throw_in(play, "away", (0.4, 1.0))
    event = play.emit.events[0]
    assert isinstance(event, ThrowInEvent)
    assert event.team == "away"
    assert play.state.carrier.player_id == event.taker_id
    assert (play.state.ball_x, play.state.ball_y) == (0.4, 1.0)
    assert 5.0 < seconds < 15.0


def test_goal_kick__the_keeper_takes_it_near_his_own_goal() -> None:
    play = _play()
    seconds = goal_kick(play, "away")
    event = play.emit.events[0]
    assert isinstance(event, GoalKickEvent)
    assert event.taker_id == play.state.away.keeper.player_id
    assert play.state.ball_x > 0.9  # away defends the x = 1 end in the first half
    assert seconds > 10.0


def test_defending_side_of_goal__follows_attack_directions_and_the_half() -> None:
    play = _play()
    assert defending_side_of_goal(play, 1.0) == "away"
    assert defending_side_of_goal(play, 0.0) == "home"
    play.state.home.attack_dir, play.state.away.attack_dir = -1, 1
    assert defending_side_of_goal(play, 1.0) == "home"


def test_out_of_play__over_the_touchline_the_other_side_throws_in() -> None:
    play = _play()
    out_of_play(play, (0.4, -0.01), "home")
    event = play.emit.events[0]
    assert isinstance(event, ThrowInEvent)
    assert event.team == "away"
    assert play.state.ball_y == 0.0


def test_out_of_play__attackers_over_the_goal_line_give_a_goal_kick() -> None:
    play = _play()
    out_of_play(play, (1.01, 0.5), "home")
    assert isinstance(play.emit.events[0], GoalKickEvent)
    assert play.emit.events[0].team == "away"


def test_out_of_play__defenders_over_their_own_goal_line_give_a_corner() -> None:
    play = _play()
    out_of_play(play, (1.01, 0.2), "away")
    assert isinstance(play.emit.events[0], CornerEvent)
    assert play.emit.events[0].team == "home"
    assert play.emit.events[0].side == "left"


def test_corner__takers_follow_the_flag_side_and_fall_back_to_the_best_deliverer() -> None:
    play = _play()
    team = play.state.home
    assert choose_corner_taker(team, 0.0).player_id == team.sheet.corner_takers.left
    assert choose_corner_taker(team, 1.0).player_id == team.sheet.corner_takers.right
    named = team.sheet.corner_takers.left
    team.players = [player for player in team.players if player.player_id != named]
    assert choose_corner_taker(team, 0.0).player_id != named


def test_build_duel__sends_the_configured_number_of_attackers_and_five_defenders() -> None:
    play = _play()
    taker = choose_corner_taker(play.state.home, 0.0)
    duel = build_duel(play, "home", taker)
    assert len(duel.attackers) == play.state.home.view.corner_attackers
    assert len(duel.defenders) == 5
    assert taker not in duel.attackers
    assert 0.0 <= duel.share <= 1.0


def test_build_duel__better_headers_raise_the_attackers_share() -> None:
    weak, strong = _play(), _play()
    for player in strong.state.home.players:
        player.skills = replace(player.skills, heading=95.0, jumping_reach=95.0)
    for player in weak.state.home.players:
        player.skills = replace(player.skills, heading=10.0, jumping_reach=10.0)
    share_weak = build_duel(weak, "home", weak.state.home.players[1]).share
    share_strong = build_duel(strong, "home", strong.state.home.players[1]).share
    assert share_strong > share_weak


def test_build_duel__a_better_delivery_lifts_the_share() -> None:
    poor, good = _play(), _play()
    taker_poor, taker_good = poor.state.home.players[1], good.state.home.players[1]
    taker_poor.skills = replace(taker_poor.skills, set_piece_delivery=5.0)
    taker_good.skills = replace(taker_good.skills, set_piece_delivery=99.0)
    assert build_duel(good, "home", taker_good).share > build_duel(poor, "home", taker_poor).share


def test_header_xg__rises_with_share_and_heading() -> None:
    play = _play()
    shooter = play.state.home.players[9]
    assert header_xg(play, shooter, 0.8) > header_xg(play, shooter, 0.2)
    strong = replace(shooter, skills=replace(shooter.skills, heading=95.0))
    assert header_xg(play, strong, 0.5) > header_xg(play, shooter, 0.5)


def test_aerial_strengths__are_on_the_attribute_scale() -> None:
    player = _play().state.home.players[5]
    assert 1.0 <= attacking_strength(player) <= 100.0
    assert 1.0 <= defending_strength(player) <= 100.0


def test_corner__every_branch_is_reachable_and_the_log_is_ordered() -> None:
    branches: Counter[str] = Counter()
    for seed in range(120):
        play = _play(seed)
        seconds = corner(play, "home", (1.0, 0.0))
        events = play.emit.events
        assert isinstance(events[0], CornerEvent)
        assert seconds > 15.0
        if any(isinstance(e, ShotEvent) for e in events):
            branches["header"] += 1
        elif any(isinstance(e, ClearanceEvent) for e in events):
            branches["cleared"] += 1
        else:
            branches["claimed"] += 1
    assert set(branches) == {"header", "cleared", "claimed"}


def _failing_pass(seed: int, cfg: SimConfig) -> Play:
    play = make_play(seed, config=cfg)
    options = generate_options(play.state, 0.1, team_weights(play.state, play.cfg), play.cfg)
    option = next(o for o in options if o.kind is ActionKind.PASS)
    resolve_pass(play, replace(option, probability=0.0))
    return play


def test_resolve_pass__with_restarts_off_no_restart_event_ever_appears() -> None:
    for seed in range(60):
        play = _failing_pass(seed, SimConfig())
        assert not any(
            isinstance(e, ThrowInEvent | GoalKickEvent | CornerEvent) for e in play.emit.events
        )


def test_resolve_pass__with_restarts_on_overhit_passes_lead_to_restarts_or_loose_balls() -> None:
    cfg = merge_config(
        SimConfig(), {"restarts": {"enabled": True, "overhit_min_m": 20.0, "overhit_max_m": 40.0}}
    )
    outcomes: Counter[str] = Counter()
    for seed in range(200):
        play = _failing_pass(seed, cfg)
        outcome = next(e for e in play.emit.events if isinstance(e, PassEvent)).outcome
        restarted = any(
            isinstance(e, ThrowInEvent | GoalKickEvent | CornerEvent) for e in play.emit.events
        )
        assert restarted == (outcome == "out")
        outcomes[outcome] += 1
    assert set(outcomes) == {"intercepted", "incomplete", "out"}


def test_resolve_clearance__with_restarts_on_some_clearances_go_into_touch() -> None:
    cfg = merge_config(SimConfig(), {"restarts": {"enabled": True, "clearance_out_share": 1.0}})
    play = make_play(config=cfg)
    option = Option(ActionKind.CLEAR, 1.0, 0.5, (0.6, 0.5), 0.9)
    resolve_clearance(play, option)
    assert isinstance(play.emit.events[-1], ThrowInEvent)


def test_resolve_dribble__a_heavy_touch_can_run_out_of_play() -> None:
    cfg = merge_config(SimConfig(), {"restarts": {"enabled": True, "dribble_out_share": 1.0}})
    for seed in range(60):
        play = make_play(seed, config=cfg)
        options = generate_options(play.state, 0.1, team_weights(play.state, play.cfg), play.cfg)
        option = next(o for o in options if o.kind is ActionKind.DRIBBLE)
        resolve_dribble(play, replace(option, probability=0.0))
        if any(isinstance(e, ThrowInEvent) for e in play.emit.events):
            return
    pytest.fail("no throw-in after a lost dribble")
