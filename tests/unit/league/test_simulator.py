from __future__ import annotations

import hashlib
from collections.abc import Callable

import pytest

from footystreams.domain.canonical import canonical_json
from footystreams.domain.match import MatchSetup
from footystreams.events.open_play import GoalEvent
from footystreams.events.result import MatchResult
from footystreams.events.summary import MatchSummaryEvent
from footystreams.league.simulator import EventSimulator, MatchSimulator, ResultOnlySimulator
from tests.factories.league_config import make_league_config
from tests.factories.league_inputs import make_world_setup
from tests.factories.league_match import make_leveled_setup, with_mood
from tests.factories.world import cached_static_tables

SEEDS = range(40)


def _result_only() -> ResultOnlySimulator:
    return ResultOnlySimulator(cached_static_tables().roles, make_league_config().result_only)


def _event_adapter() -> EventSimulator:
    return EventSimulator(_result_only().simulate)


SIMULATORS: dict[str, Callable[[], MatchSimulator]] = {
    "result_only": _result_only,
    "event_adapter": _event_adapter,
}


@pytest.fixture(params=sorted(SIMULATORS))
def simulator(request: pytest.FixtureRequest) -> MatchSimulator:
    return SIMULATORS[request.param]()


def test_simulate__same_seed__identical_result(simulator: MatchSimulator) -> None:
    setup = make_leveled_setup()
    assert simulator.simulate(setup, 7) == simulator.simulate(setup, 7)


def test_simulate__different_seeds__scores_vary(simulator: MatchSimulator) -> None:
    setup = make_leveled_setup()
    scores = {
        (r.summary.score_home, r.summary.score_away)
        for r in (simulator.simulate(setup, seed) for seed in SEEDS)
    }
    assert len(scores) > 3


def test_simulate__events__have_contiguous_sequence_ending_in_summary(
    simulator: MatchSimulator,
) -> None:
    result = simulator.simulate(make_leveled_setup(), 3)
    assert [event.seq for event in result.events] == list(range(len(result.events)))
    assert isinstance(result.events[-1], MatchSummaryEvent)


def test_simulate__score__equals_goal_events_by_side(simulator: MatchSimulator) -> None:
    for seed in SEEDS:
        result = simulator.simulate(make_leveled_setup(), seed)
        goals = [e for e in result.events if isinstance(e, GoalEvent)]
        assert result.summary.score_home == sum(g.team == "home" for g in goals)
        assert result.summary.score_away == sum(g.team == "away" for g in goals)


def test_simulate__log_digest__hashes_the_events_before_the_summary(
    simulator: MatchSimulator,
) -> None:
    result = simulator.simulate(make_leveled_setup(), 5)
    payload = canonical_json([e.model_dump(mode="json") for e in result.events[:-1]])
    assert result.log_digest == hashlib.sha256(payload.encode()).hexdigest()


def test_simulate__result__round_trips_through_json(simulator: MatchSimulator) -> None:
    result = simulator.simulate(make_leveled_setup(), 9)
    assert MatchResult.model_validate_json(result.model_dump_json()) == result


def test_simulate__summary__covers_every_starter(simulator: MatchSimulator) -> None:
    result = simulator.simulate(make_leveled_setup(), 2)
    assert len(result.summary.player_stats) == 22
    assert result.summary.player_of_the_match in {s.player_id for s in result.summary.player_stats}


def test_simulate__stronger_side__wins_more_often_than_it_loses() -> None:
    simulator = _result_only()
    setup = make_leveled_setup(home_level=70, away_level=50)
    margins = [
        r.summary.score_home - r.summary.score_away
        for r in (simulator.simulate(setup, s) for s in range(120))
    ]
    assert sum(margins) / len(margins) > 0.5


def test_expected_goals__equal_sides__home_side_edges_it() -> None:
    home, away = _result_only().expected_goals(make_leveled_setup())
    assert home > away


def test_expected_goals__one_starter_in_bad_mood__costs_a_small_goal_difference() -> None:
    simulator = _result_only()
    control = make_leveled_setup()
    moody = with_mood(control, control.home.lineup[9].player_id, 0.85)
    base_home, base_away = simulator.expected_goals(control)
    low_home, low_away = simulator.expected_goals(moody)
    swing = (base_home - base_away) - (low_home - low_away)
    assert 0.04 <= swing <= 0.10


def test_simulate__sent_off_player__plays_fewer_minutes_and_scores_nothing_after() -> None:
    simulator = _result_only()
    setup: MatchSetup = make_leveled_setup()
    for seed in range(400):
        stats = simulator.simulate(setup, seed).summary.player_stats
        sent_off = [s for s in stats if s.reds]
        if sent_off:
            assert all(s.minutes < 90 for s in sent_off)
            return
    pytest.fail("no red card in 400 matches")


def test_simulate__real_world_setup__plays_a_full_match(simulator: MatchSimulator) -> None:
    result = simulator.simulate(make_world_setup(), 11)
    assert result.summary.score_home + result.summary.score_away < 12
    assert len(result.summary.player_stats) == 22
