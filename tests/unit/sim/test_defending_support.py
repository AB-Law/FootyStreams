from dataclasses import replace

from footystreams.sim.config import PositionConfig
from footystreams.sim.defending import (
    balance_spot,
    cover_spot,
    lane_cutting_spots,
    plan_defending,
)
from footystreams.sim.geometry import PITCH_LENGTH_M, Point, frame_coordinate
from footystreams.sim.state import Line, MatchState
from footystreams.sim.support import ANGLES, support_spots, support_weight
from tests.factories.match import make_setup
from tests.factories.sim_play import make_state

CFG = PositionConfig()


def _state() -> MatchState:
    return make_state(make_setup())


def _frame_spot(state: MatchState, player: object) -> Point:
    team = state.away  # the away side defends in the frame these tests use
    return frame_coordinate(player.x, team.attack_dir), frame_coordinate(player.y, team.attack_dir)  # type: ignore[attr-defined]


def _rivals(state: MatchState) -> list[tuple[object, Point]]:
    return [
        (rival, _frame_spot(state, rival))
        for rival in state.home.players
        if rival.line is not Line.KEEPER
    ]


def test_lane_cutting_spots__a_defender_stands_on_the_lane_toward_a_receiver() -> None:
    state = _state()
    team = state.away
    carrier = (0.5, 0.5)
    receiver_player = state.home.players[8]
    receiver = (0.45, 0.62)
    free = [(team.players[4], (0.48, 0.55))]
    spots = lane_cutting_spots(free, [(receiver_player, receiver)], carrier, CFG)
    spot = spots[team.players[4].slot]
    assert spot[0] == carrier[0] + CFG.shadow_share * (receiver[0] - carrier[0])
    assert spot[1] == carrier[1] + CFG.shadow_share * (receiver[1] - carrier[1])


def test_lane_cutting_spots__a_receiver_behind_the_carrier_is_not_cut_off() -> None:
    state = _state()
    free = [(state.away.players[4], (0.5, 0.5))]
    behind = (0.7, 0.5)  # further from the defending goal than the carrier: a back pass
    assert lane_cutting_spots(free, [(state.home.players[8], behind)], (0.5, 0.5), CFG) == {}


def test_lane_cutting_spots__only_the_configured_number_of_lanes_are_cut() -> None:
    state = _state()
    two = CFG.model_copy(update={"lane_cut_count": 2})
    free = [(state.away.players[i], (0.5, 0.4 + 0.05 * i)) for i in (3, 4, 5)]
    receivers = [(state.home.players[7], (0.45, 0.55)), (state.home.players[8], (0.4, 0.45))]
    assert len(lane_cutting_spots(free, receivers, (0.5, 0.5), two)) == 2
    assert len(lane_cutting_spots(free, receivers, (0.5, 0.5), CFG)) == 1


def test_lane_cutting_spots__a_defender_too_far_from_the_lane_does_not_come() -> None:
    state = _state()
    free = [(state.away.players[4], (0.02, 0.02))]
    assert lane_cutting_spots(free, [(state.home.players[8], (0.4, 0.5))], (0.5, 0.5), CFG) == {}


def test_cover_spot__stands_behind_the_presser_and_toward_the_middle() -> None:
    spot = cover_spot((0.6, 0.2), (0.62, 0.2), CFG)
    assert spot[0] < 0.6
    assert spot[1] > 0.2


def test_balance_spot__shifts_across_toward_the_ball_side() -> None:
    assert balance_spot((0.3, 0.8), (0.5, 0.2), CFG) == (0.3, 0.8 + CFG.balance_pull * (0.2 - 0.8))


def test_plan_defending__every_free_defender_gets_a_job() -> None:
    state = _state()
    team = state.away
    free = [
        (p, (p.base_x, p.base_y)) for p in team.players if p.line in (Line.DEFENCE, Line.MIDFIELD)
    ]
    ball = (0.4, 0.5)
    plan = plan_defending(team, state.home, free, (ball, (0.38, 0.5)), CFG)
    assert set(plan) == {player.slot for player, _ in free}
    assert all(0.0 <= weight <= 1.0 for _, weight in plan.values())


def test_plan_defending__a_free_defender_with_nobody_near_still_picks_up_a_runner() -> None:
    state = _state()
    team = state.away
    free = [(team.players[1], (0.1, 0.05))]  # far from everyone: the wide range finds a man
    plan = plan_defending(team, state.home, free, ((0.5, 0.5), (0.48, 0.5)), CFG)
    assert team.players[1].slot in plan


def test_support_spots__the_nearest_teammates_take_different_angles_round_the_carrier() -> None:
    state = _state()
    team = state.home
    carrier = (0.5, 0.5)
    movers = [
        (player, (0.5 + 0.01 * i, 0.5 + 0.02 * i)) for i, player in enumerate(team.players[1:8])
    ]
    spots = support_spots(movers, carrier, [], CFG)
    assert len(spots) == CFG.support_count
    assert len(set(spots.values())) == CFG.support_count
    for spot in spots.values():
        gap_m = max(abs(spot[0] - carrier[0]) * PITCH_LENGTH_M, abs(spot[1] - carrier[1]) * 68)
        assert gap_m <= max(abs(a) for angle in ANGLES for a in angle) + 1e-6


def test_support_spots__an_angle_a_defender_stands_on_is_avoided() -> None:
    state = _state()
    mover = state.home.players[5]
    carrier = (0.5, 0.5)
    open_choice = support_spots([(mover, (0.52, 0.5))], carrier, [], CFG)[mover.slot]
    blocked = support_spots([(mover, (0.52, 0.5))], carrier, [open_choice], CFG)[mover.slot]
    assert blocked != open_choice  # cut off: he drifts to the next best angle


def test_support_spots__teammates_out_of_range_are_not_asked() -> None:
    state = _state()
    far = [(state.home.players[5], (0.05, 0.05))]
    assert support_spots(far, (0.9, 0.9), [], CFG) == {}


def test_support_weight__sharper_off_the_ball_movers_commit_more() -> None:
    state = _state()
    player = state.home.players[9]
    keen = replace(player, skills=replace(player.skills, off_ball_movement=90.0))
    lazy = replace(player, skills=replace(player.skills, off_ball_movement=20.0))
    assert support_weight(keen, CFG) > support_weight(lazy, CFG)
    assert 0.0 <= support_weight(keen, CFG) <= 1.0
