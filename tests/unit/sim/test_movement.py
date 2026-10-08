from footystreams.sim.config import PositionConfig
from footystreams.sim.geometry import PITCH_LENGTH_M, distance_m, frame_coordinate
from footystreams.sim.movement import assign_marks, choose_pressers, wander
from footystreams.sim.positioning import update_positions
from footystreams.sim.state import Line, MatchState
from tests.factories.match import make_setup
from tests.factories.sim_play import make_state

CFG = PositionConfig()


def _state() -> MatchState:
    return make_state(make_setup())


def test_wander__a_goalkeeper_never_wanders() -> None:
    state = _state()
    assert wander(state.home.keeper, 123.0, in_possession=True, cfg=CFG) == (0.0, 0.0)


def test_wander__stays_inside_the_configured_loop_and_is_never_still() -> None:
    state = _state()
    striker = state.home.players[10]
    reach = CFG.wander_m[Line.ATTACK] * 1.5  # the widest a sharp mover loops, in metres
    offsets = [wander(striker, float(t), in_possession=True, cfg=CFG) for t in range(0, 40, 2)]
    assert all(abs(x) * PITCH_LENGTH_M <= reach + 1e-9 for x, _ in offsets)
    assert len({round(x, 6) for x, _ in offsets}) > 5


def test_wander__neighbours_do_not_move_in_step() -> None:
    state = _state()
    first = wander(state.home.players[9], 7.0, in_possession=True, cfg=CFG)
    second = wander(state.home.players[10], 7.0, in_possession=True, cfg=CFG)
    assert first != second


def test_wander__is_a_pure_function_of_the_clock() -> None:
    state = _state()
    player = state.away.players[5]
    assert wander(player, 31.5, in_possession=False, cfg=CFG) == wander(
        player, 31.5, in_possession=False, cfg=CFG
    )


def test_choose_pressers__nearest_outfield_players_and_never_the_keeper() -> None:
    state = _state()
    team = state.home
    ball = (team.keeper.x, team.keeper.y)  # the keeper is the nearest man to the ball
    pressers = choose_pressers(team, ball, CFG)
    assert team.keeper.slot not in pressers
    assert 1 <= len(pressers) <= 3


def test_choose_pressers__harder_pressing_sends_more_men() -> None:
    state = _state()
    team = state.home
    ball = (0.5, 0.5)
    quiet = choose_pressers(team, ball, CFG.model_copy(update={"press_count": 0.5}))
    hard = choose_pressers(team, ball, CFG.model_copy(update={"press_count": 4.0}))
    assert len(hard) > len(quiet)


def test_assign_marks__each_man_is_marked_once_and_goal_side() -> None:
    state = _state()
    team, rivals = state.home, state.away
    free = [
        (player, (player.base_x, player.base_y))
        for player in team.players
        if player.line is Line.DEFENCE
    ]
    spots = assign_marks(team, rivals, free, CFG)
    assert spots
    assert len(spots) == len(set(spots.values()))
    for player, _ in free:
        spot = spots.get(player.slot)
        if spot is None:
            continue
        rival_x = [frame_coordinate(r.x, team.attack_dir) for r in rivals.players]
        assert any(
            abs(spot[0] + CFG.marking_goalside_m / PITCH_LENGTH_M - x) < 1e-9 for x in rival_x
        )


def test_assign_marks__a_man_out_of_range_is_left_alone() -> None:
    state = _state()
    tight = CFG.model_copy(update={"marking_range_m": 0.5})
    free = [(state.home.players[1], (0.05, 0.05))]
    assert assign_marks(state.home, state.away, free, tight) == {}


def test_update_positions__nobody_is_sent_to_the_touchline() -> None:
    state = _state()
    margin = CFG.edge_margin
    for _ in range(60):
        state.t_period += 2.0
        update_positions(state, 2.0, CFG)
    for team in (state.home, state.away):
        for player in team.players:
            assert margin - 1e-9 <= player.y <= 1.0 - margin + 1e-9


def test_update_positions__the_nearest_defender_closes_on_the_carrier() -> None:
    state = _state()
    carrier = state.carrier
    state.ball_x, state.ball_y = carrier.x, carrier.y  # the ball is where its carrier is
    defenders = state.defenders
    nearest = min(
        (p for p in defenders.players if p.line is not Line.KEEPER),
        key=lambda p: distance_m(p.x, p.y, carrier.x, carrier.y),
    )
    before = distance_m(nearest.x, nearest.y, carrier.x, carrier.y)
    update_positions(state, 4.0, CFG)
    assert distance_m(nearest.x, nearest.y, carrier.x, carrier.y) < before
