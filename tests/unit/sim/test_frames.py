from functools import cache

import pytest

from footystreams.domain.types import PlayerId
from footystreams.events.result import MatchResult
from footystreams.events.structure import FrameEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.sim.frames import (
    MAX_CARRY_M,
    MAX_SPEED_MPS,
    FrameRecorder,
    Snapshot,
    _FrameView,
    _Moment,
)
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
    assert fastest <= MAX_SPEED_MPS + 0.1  # restarts place players far away; frames make them run


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


A, B, C = PlayerId("a"), PlayerId("b"), PlayerId("c")


def _snapshot(t: float, ball: float, carrier: PlayerId, c_x: float) -> Snapshot:
    return Snapshot(
        t=t,
        ball=(ball, 0.5),
        carrier=carrier,
        players={A: (0.2, 0.5), B: (ball if carrier == B else 0.5, 0.5), C: (c_x, 0.2)},
    )


def test_moment__a_short_pass_is_held_and_jogged_then_flies_and_lands_with_the_receiver() -> None:
    start, end = _snapshot(0.0, 0.2, A, 0.7), _snapshot(4.0, 0.5, B, 0.9)
    moment = _Moment.of(start, end)
    early = _FrameView(moment, 1.0)
    assert early.carrier() == A
    assert early.ball()[0] > 0.2  # he jogs on with it toward the man he will pass to
    assert early.positions()[A][0] > 0.2
    landed = _FrameView(moment, 4.0)
    assert landed.carrier() == B
    assert landed.ball() == (0.5, 0.5)
    assert landed.positions()[A] == (0.2, 0.5)  # back where the sim has him: no jump next moment
    assert landed.positions()[B] == (0.5, 0.5)


def test_moment__the_passer_never_jogs_further_than_the_cap() -> None:
    moment = _Moment.of(_snapshot(0.0, 0.1, A, 0.7), _snapshot(4.0, 0.9, B, 0.9))
    furthest = max(abs(_FrameView(moment, t / 10).positions()[A][0] - 0.2) for t in range(41))
    assert furthest * 105 <= MAX_CARRY_M + 0.1


def test_moment__a_long_moment_shows_the_ball_arrive_first_and_then_the_wait() -> None:
    start, end = _snapshot(0.0, 0.2, A, 0.7), _snapshot(14.0, 0.5, B, 0.9)
    moment = _Moment.of(start, end)
    early = _FrameView(moment, 2.0)
    assert early.ball() == (0.5, 0.5)
    assert early.carrier() == B
    assert early.positions()[B] == (0.5, 0.5)
    assert early.positions()[C][0] < 0.75  # a team-mate is still walking to his place


def test_moment__a_carried_ball_travels_with_its_carrier_all_the_way() -> None:
    start, end = _snapshot(0.0, 0.2, A, 0.7), _snapshot(3.0, 0.3, A, 0.7)
    half = _FrameView(_Moment.of(start, end), 1.5)
    assert abs(half.ball()[0] - 0.25) < 1e-9
    assert half.carrier() == A


def test_recorder__a_player_the_sim_moves_far_runs_there_at_a_sprint_not_instantly() -> None:
    play = make_play(config=FRAMES)
    state = play.state
    runner = state.home.players[3]
    recorder = FrameRecorder(1)
    recorder.reset(state)
    start_x = runner.x
    runner.x = start_x + 0.5  # 52 m in one step
    state.t_period = 1.0
    recorder.record(state, play.emit)
    frame = next(e for e in play.emit.events if isinstance(e, FrameEvent))
    shown = next(p for p in frame.players if p.player_id == runner.player_id)
    assert (shown.x - start_x) * 105 == pytest.approx(MAX_SPEED_MPS, abs=0.05)


def test_recorder__the_ball_is_loose_until_its_carrier_has_reached_it() -> None:
    far, near = (0.1, 0.5), (0.1 + 1.0 / 105, 0.5)
    positions = {A: far}
    assert FrameRecorder._controlling(A, positions, (0.5, 0.5)) is None
    assert FrameRecorder._controlling(A, {A: near}, far) == A
    assert FrameRecorder._controlling(None, positions, far) is None
