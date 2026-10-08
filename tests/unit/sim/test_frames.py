from functools import cache

import pytest

from footystreams.events.result import MatchResult
from footystreams.events.structure import FrameEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.sim.frames import FrameRecorder
from tests.factories.sim_play import make_play
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import without_frames_renumbered
from tests.helpers.sim import assert_match_valid

FRAMES = merge_config(SimConfig(), {"emit_frames": True, "frame_interval_s": 5})


@cache
def _with_frames() -> MatchResult:
    return run_match(make_demo_setup(), 3, FRAMES, default_tables())


@cache
def _without_frames() -> MatchResult:
    return run_match(make_demo_setup(), 3, SimConfig(), default_tables())


def test_frames__are_off_by_default() -> None:
    assert not any(isinstance(e, FrameEvent) for e in _without_frames().events)


def test_frames__a_match_with_frames_is_valid_and_has_one_every_interval() -> None:
    result = _with_frames()
    assert_match_valid(result.events, make_demo_setup())
    frames = [e for e in result.events if isinstance(e, FrameEvent)]
    assert len(frames) == pytest.approx(result.summary.duration_s / 5, rel=0.05)
    assert all(len(frame.players) >= 9 for frame in frames)
    assert len(frames[0].players) == 22


def test_frames__switching_them_on_changes_no_other_event() -> None:
    on = without_frames_renumbered(_with_frames().events)
    off = without_frames_renumbered(_without_frames().events)
    assert on == off


def test_frames__players_do_not_teleport_between_frames() -> None:
    frames = [e for e in _with_frames().events if isinstance(e, FrameEvent)]
    fastest = max(p.speed_mps for frame in frames[1:] for p in frame.players)
    assert fastest < 60.0  # kick-off and restarts jump players, but never across the pitch twice


def test_frames__the_summary_ignores_them() -> None:
    on, off = _with_frames().summary, _without_frames().summary
    assert on.team_stats_home == off.team_stats_home
    assert on.player_stats == off.player_stats


def test_recorder__a_frame_between_two_steps_is_halfway_between_their_positions() -> None:
    play = make_play(config=FRAMES)
    state = play.state
    mover = state.home.players[3]
    recorder = FrameRecorder(1)
    recorder.reset(state)
    start_x = mover.x
    mover.x = start_x + 0.1
    state.t_period = 2.0
    recorder.record(state, play.emit)
    frames = [e for e in play.emit.events if isinstance(e, FrameEvent)]
    assert [frame.clock.second for frame in frames] == [1, 2]
    halfway = next(p for p in frames[0].players if p.player_id == mover.player_id)
    assert halfway.x == pytest.approx(start_x + 0.05, abs=1e-4)
    assert frames[1].players[3].x == pytest.approx(start_x + 0.1, abs=1e-4)
    assert state.t_period == 2.0  # the clock is put back


def test_recorder__before_a_reset_it_records_nothing() -> None:
    play = make_play(config=FRAMES)
    FrameRecorder(1).record(play.state, play.emit)
    assert not play.emit.events


def test_frames__with_context_on_they_still_change_no_other_event() -> None:
    plain = merge_config(SimConfig(), {"context": {"enabled": True}})
    tracked = merge_config(plain, {"emit_frames": True, "frame_interval_s": 10})
    off = run_match(make_demo_setup(), 5, plain, default_tables()).events
    on = run_match(make_demo_setup(), 5, tracked, default_tables()).events
    assert without_frames_renumbered(on) == without_frames_renumbered(off)
