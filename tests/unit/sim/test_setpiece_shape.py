from math import hypot

from footystreams.sim.geometry import (
    PENALTY_AREA_DEPTH,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    frame_coordinate,
)
from footystreams.sim.play import Play
from footystreams.sim.setpiece_shape import (
    WALL_DISTANCE_M,
    corner_layout,
    free_kick_layout,
    goal_kick_layout,
    penalty_layout,
    settle,
    throw_in_layout,
)
from footystreams.sim.state import Line, PlayerState
from tests.factories.sim_play import make_play


def _play() -> Play:
    return make_play()


def _taker(play: Play) -> PlayerState:
    return next(p for p in play.state.home.players if p.line is Line.MIDFIELD)


def test_throw_in_layout__three_team_mates_show_and_three_opponents_pick_them_up() -> None:
    play = _play()
    state, taking = play.state, play.state.home
    layout = throw_in_layout(state, taking, _taker(play), (0.5, 0.0))
    teams = [player.side for player, _ in layout]
    assert teams.count("home") == 3
    assert teams.count("away") == 3


def test_throw_in_layout__the_options_stand_infield_of_the_touchline() -> None:
    play = _play()
    layout = throw_in_layout(play.state, play.state.home, _taker(play), (0.5, 0.0))
    assert all(spot[1] > 0.0 for player, spot in layout if player.side == "home")


def test_corner_layout__attackers_crowd_the_box_and_the_keeper_stays_on_his_line() -> None:
    play = _play()
    state, taking = play.state, play.state.home
    layout = corner_layout(state, taking, _taker(play), (1.0, 0.0), 4)
    attackers = [spot for player, spot in layout if player.side == "home"]
    assert sum(1 for x, _ in attackers if x > 1.0 - PENALTY_AREA_DEPTH) >= 4
    keeper = next(spot for player, spot in layout if player is state.away.keeper)
    assert keeper[0] > 0.95


def test_corner_layout__every_man_in_the_box_is_picked_up_by_a_defender() -> None:
    play = _play()
    layout = corner_layout(play.state, play.state.home, _taker(play), (1.0, 1.0), 4)
    defenders = [
        spot for player, spot in layout if player.side == "away" and player.line is not Line.KEEPER
    ]
    assert len(defenders) >= 6  # two on the posts and one for each attacker


def test_free_kick_layout__the_wall_stands_nine_metres_from_the_ball() -> None:
    play = _play()
    state, taking = play.state, play.state.home
    spot = (0.78, 0.4)
    layout = free_kick_layout(state, taking, _taker(play), spot, shooting=True)
    wall = [
        point
        for player, point in layout
        if player.side == "away" and player.line is not Line.KEEPER and point[0] < 0.88
    ]
    assert len(wall) >= 3
    gaps = [hypot((x - spot[0]) * PITCH_LENGTH_M, (y - spot[1]) * PITCH_WIDTH_M) for x, y in wall]
    assert all(abs(gap - WALL_DISTANCE_M) < 2.0 for gap in gaps)


def test_free_kick_layout__a_kick_out_of_range_is_just_outlets_round_the_taker() -> None:
    play = _play()
    layout = free_kick_layout(play.state, play.state.home, _taker(play), (0.3, 0.5), shooting=False)
    assert {player.side for player, _ in layout} == {"home"}


def test_goal_kick_layout__the_taking_side_spreads_and_the_other_presses_high() -> None:
    play = _play()
    layout = goal_kick_layout(play.state, play.state.home)
    forwards = [spot for player, spot in layout if player.side == "away"]
    assert forwards
    assert all(x < 0.3 for x, _ in forwards)


def test_penalty_layout__only_the_taker_and_the_keeper_are_inside_the_box() -> None:
    play = _play()
    state, taking = play.state, play.state.home
    taker = _taker(play)
    layout = penalty_layout(state, taking, taker)
    inside = [player for player, (x, _) in layout if x > 1.0 - PENALTY_AREA_DEPTH]
    assert inside == [state.away.keeper]


def test_settle__players_walk_toward_their_places_but_no_faster_than_they_can() -> None:
    play = _play()
    state, taking = play.state, play.state.home
    layout = goal_kick_layout(state, taking)
    before = {player.player_id: (player.x, player.y) for player, _ in layout}
    settle(play, taking, layout, 0.5, keyframe=False)
    for player, _ in layout:
        x0, y0 = before[player.player_id]
        moved = hypot((player.x - x0) * PITCH_LENGTH_M, (player.y - y0) * PITCH_WIDTH_M)
        assert moved <= 12.0 * 0.5 + 1e-9  # nobody covers more than a sprinter's half second


def test_settle__records_a_mid_moment_snapshot_only_when_frames_are_on_and_asked_for() -> None:
    play = _play()
    state, taking = play.state, play.state.home
    layout = goal_kick_layout(state, taking)
    settle(play, taking, layout, 5.0, keyframe=True)
    assert state.keyframes == []
    state.record_keyframes = True
    settle(play, taking, layout, 5.0, keyframe=False)
    assert state.keyframes == []
    settle(play, taking, layout, 5.0, keyframe=True)
    assert [k.t for k in state.keyframes] == [state.t_period + 5.0]
    assert frame_coordinate(0.0, 1) == 0.0
