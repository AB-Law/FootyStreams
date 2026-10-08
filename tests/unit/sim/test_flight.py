import pytest

from footystreams.events.open_play import ShotEvent
from footystreams.sim.flight import HALF_GOAL, shot_flight
from footystreams.sim.play import Play
from tests.factories.sim_play import make_play
from tests.helpers.logs import context_result

OUTCOMES = ("goal", "saved", "blocked", "off_target", "woodwork")


def _play(seed: int = 1) -> Play:
    play = make_play(seed=seed)
    shooter = play.state.carrier
    shooter.x, shooter.y = 0.8, 0.35  # home attacks +x, on the shooter's left of the goal
    return play


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_shot_flight__always_four_draws_from_the_flight_stream_only(outcome: str) -> None:
    play = _play()
    shot_flight(play, play.state.carrier, outcome)
    assert play.flight.draws == 4
    assert play.rng.draws == 0


def test_shot_flight__a_goal_ends_inside_the_posts_on_the_goal_line() -> None:
    for seed in range(20):
        play = _play(seed)
        path = shot_flight(play, play.state.carrier, "goal")
        assert path.target[0] == 1.0
        assert abs(path.target[1] - 0.5) < HALF_GOAL


def test_shot_flight__a_miss_ends_outside_the_posts() -> None:
    for seed in range(20):
        play = _play(seed)
        path = shot_flight(play, play.state.carrier, "off_target")
        assert abs(path.target[1] - 0.5) > HALF_GOAL


def test_shot_flight__a_block_stops_the_ball_short_of_goal() -> None:
    play = _play()
    path = shot_flight(play, play.state.carrier, "blocked")
    assert 0.8 < path.target[0] < 1.0


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_shot_flight__bend_pace_and_loft_stay_in_range(outcome: str) -> None:
    for seed in range(20):
        play = _play(seed)
        path = shot_flight(play, play.state.carrier, outcome)
        assert -1.0 <= path.curve <= 1.0
        assert 20.0 <= path.speed_mps <= 34.0
        assert 0.0 <= path.loft <= 1.0


def test_shot_flight__same_seed_gives_the_same_path() -> None:
    first, second = _play(5), _play(5)
    assert shot_flight(first, first.state.carrier, "goal") == shot_flight(
        second, second.state.carrier, "goal"
    )


def test_run_match__every_shot_event_carries_its_flight() -> None:
    shots = [e for e in context_result().events if isinstance(e, ShotEvent)]
    assert shots
    assert all(e.target is not None and e.speed_mps >= 20.0 for e in shots)
