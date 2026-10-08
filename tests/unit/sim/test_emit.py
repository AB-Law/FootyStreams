import pytest
from pydantic import ValidationError

from footystreams.domain.types import MatchId, PlayerId
from footystreams.events.context import ContextTag
from footystreams.events.open_play import PassEvent, ShotEvent
from footystreams.sim.emit import EventEmitter, Meta, participant, phase_of, significance
from footystreams.sim.positioning import place_for_kickoff
from footystreams.sim.rng import SimRng
from footystreams.sim.state import MatchState, build_state
from footystreams.sim.tables import default_tables
from tests.factories.match import make_setup


def _state() -> MatchState:
    state = build_state(make_setup(), default_tables(), SimRng(1))
    place_for_kickoff(state, "home")
    return state


def test_emit__numbers_events_and_builds_ids_from_the_match_id() -> None:
    state, emitter = _state(), EventEmitter(MatchId("mch_test0001"))
    first = emitter.emit(state, PassEvent, Meta(team="home"), from_player_id=PlayerId("plr_a"))
    second = emitter.emit(state, PassEvent, Meta(team="home"), from_player_id=PlayerId("plr_a"))
    assert (first, second) == ("mch_test0001:00000", "mch_test0001:00001")
    assert [event.seq for event in emitter.events] == [0, 1]


def test_emit__stamps_clock_score_and_attack_direction_from_state() -> None:
    state, emitter = _state(), EventEmitter(MatchId("mch_test0001"))
    state.period, state.t_period, state.tick = 2, 125.0, 9
    state.home.score = 2
    emitter.emit(state, PassEvent, Meta(team="away"), from_player_id=PlayerId("plr_a"))
    event = emitter.events[0]
    assert (event.clock.period, event.clock.minute, event.clock.second) == (2, 47, 5)
    assert event.tick == 9
    assert event.ctx.score_home == 2
    assert event.ctx.attack_dir == -1


def test_emit__position_is_clamped_into_the_pitch() -> None:
    state, emitter = _state(), EventEmitter(MatchId("mch_test0001"))
    emitter.emit(state, PassEvent, Meta(pos=(1.4, -0.2)), from_player_id=PlayerId("plr_a"))
    pos = emitter.events[0].pos
    assert pos is not None
    assert (pos.x, pos.y) == (1.0, 0.0)


def test_emit__invalid_fields_are_rejected_by_the_model() -> None:
    state, emitter = _state(), EventEmitter(MatchId("mch_test0001"))
    with pytest.raises(ValidationError):
        emitter.emit(state, PassEvent, Meta(), from_player_id=PlayerId("plr_a"), outcome="bogus")


def test_emit__carries_participants_tags_and_headline() -> None:
    state, emitter = _state(), EventEmitter(MatchId("mch_test0001"))
    meta = Meta(
        participants=(participant(PlayerId("plr_a"), "shooter"),),
        headline="Brae shoots",
        tags=(ContextTag.PRESSURE,),
    )
    emitter.emit(state, ShotEvent, meta, player_id=PlayerId("plr_a"), xg=0.12)
    event = emitter.events[0]
    assert event.participants[0].role == "shooter"
    assert event.ctx.headline == "Brae shoots"
    assert event.ctx.significance > 0.15


def test_drain__returns_only_events_emitted_since_the_last_drain() -> None:
    state, emitter = _state(), EventEmitter(MatchId("mch_test0001"))
    emitter.emit(state, PassEvent, Meta(), from_player_id=PlayerId("plr_a"))
    assert len(emitter.drain()) == 1
    assert emitter.drain() == []
    emitter.emit(state, PassEvent, Meta(), from_player_id=PlayerId("plr_a"))
    assert len(emitter.drain()) == 1


def test_phase_of__follows_the_ball_in_the_possessing_teams_frame() -> None:
    state = _state()
    state.ball_x = 0.2
    assert phase_of(state) == "build_up"
    state.ball_x = 0.5
    assert phase_of(state) == "progression"
    state.ball_x = 0.9
    assert phase_of(state) == "final_third"


def test_significance__goal_is_maximal_and_shots_scale_with_xg() -> None:
    assert significance("goal", 0.0) == 1.0
    assert significance("shot", 0.3) > significance("shot", 0.05) > significance("pass", 0.0)
