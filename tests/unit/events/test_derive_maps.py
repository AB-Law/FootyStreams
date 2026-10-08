import pytest

from footystreams.events.derive.maps import (
    key_moments,
    momentum_timeline,
    pass_matrix,
    shot_map,
    xg_timeline,
    zone_pass_flow,
)
from footystreams.events.derive.threat import GRID_ROWS
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import GoalEvent, PassEvent, ShotEvent
from footystreams.events.structure import FrameEvent
from tests.factories.log_builder import LogBuilder
from tests.helpers.logs import context_result

A, B, C = "plr_home0004", "plr_home0005", "plr_home0006"
D = "plr_away0004"


def _pass(log: LogBuilder, **fields: object) -> None:
    log.add(PassEvent, from_player_id=A, to_player_id=B, **fields)  # type: ignore[arg-type]


def test_pass_matrix__counts_completed_passes_per_pair_in_sorted_order() -> None:
    log = LogBuilder()
    _pass(log)
    _pass(log)
    log.add(PassEvent, from_player_id=B, to_player_id=A)
    _pass(log, outcome="incomplete")
    log.add(PassEvent, from_player_id=A, to_player_id=None, outcome="out")
    links = pass_matrix(log.events)
    assert [(link.passer_id, link.receiver_id, link.count) for link in links] == [
        (A, B, 2),
        (B, A, 1),
    ]


def test_zone_pass_flow__bins_origin_and_end_in_the_passing_teams_frame() -> None:
    log = LogBuilder()
    log.add(
        PassEvent,
        from_player_id=A,
        to_player_id=B,
        pos={"x": 0.05, "y": 0.05},
        end_pos={"x": 0.95, "y": 0.95},
    )
    flow = zone_pass_flow(log.events)
    assert [(f.team, f.from_zone, f.to_zone, f.count) for f in flow] == [
        ("home", 0, 11 * GRID_ROWS + 7, 1)
    ]


def test_zone_pass_flow__an_away_pass_is_mirrored_into_its_own_frame() -> None:
    log = LogBuilder()
    log.add(
        PassEvent,
        team="away",
        from_player_id=D,
        to_player_id=D,
        pos={"x": 0.95, "y": 0.95},
        end_pos={"x": 0.05, "y": 0.05},
    )
    event = log.events[0].model_copy(
        update={"ctx": log.events[0].ctx.model_copy(update={"attack_dir": -1})}
    )
    flow = zone_pass_flow([event])
    assert (flow[0].from_zone, flow[0].to_zone) == (0, 11 * GRID_ROWS + 7)


def test_zone_pass_flow__passes_without_an_end_are_left_out() -> None:
    log = LogBuilder()
    _pass(log, pos={"x": 0.3, "y": 0.3})
    assert zone_pass_flow(log.events) == ()


def test_shot_map__lists_shots_with_position_xg_and_outcome() -> None:
    log = LogBuilder()
    log.add(ShotEvent, player_id=A, xg=0.2, outcome="saved", pos={"x": 0.9, "y": 0.4})
    log.add(ShotEvent, player_id=A, xg=0.1, outcome="blocked")  # no position: skipped
    points = shot_map(log.events)
    assert [(p.team, p.x, p.y, p.xg, p.outcome) for p in points] == [
        ("home", 0.9, 0.4, 0.2, "saved")
    ]


def test_xg_timeline__accumulates_per_side_after_each_shot() -> None:
    log = LogBuilder()
    log.add(ShotEvent, player_id=A, xg=0.2, minute=10)
    log.add(ShotEvent, team="away", player_id=D, xg=0.1, minute=20)
    log.add(ShotEvent, player_id=A, xg=0.3, minute=30)
    points = xg_timeline(log.events)
    assert [(p.t, p.home, p.away) for p in points] == [
        (600, 0.2, 0.0),
        (1200, 0.2, 0.1),
        (1800, 0.5, 0.1),
    ]


def test_momentum_timeline__samples_each_minute_with_the_latest_value() -> None:
    log = LogBuilder()
    log.add(PassEvent, from_player_id=A, minute=0, second=30)
    log.add(PassEvent, from_player_id=A, minute=2, second=10)
    log.events[0] = log.events[0].model_copy(
        update={"ctx": log.events[0].ctx.model_copy(update={"momentum": 0.5})}
    )
    log.events[1] = log.events[1].model_copy(
        update={"ctx": log.events[1].ctx.model_copy(update={"momentum": -0.25})}
    )
    log.add(FrameEvent, ball_pos_x=0.5, ball_pos_y=0.5, minute=1)
    points = momentum_timeline(log.events, 180)
    assert [(p.t, p.momentum) for p in points] == [(0, 0.0), (60, 0.5), (120, 0.5), (180, -0.25)]


def test_key_moments__goals_big_chances_and_dismissals_but_not_routine_play() -> None:
    log = LogBuilder()
    _pass(log)
    log.add(GoalEvent, scorer_id=A, significance=1.0)
    log.add(ShotEvent, player_id=A, xg=0.02, outcome="blocked", significance=0.19)
    log.add(CardEvent, player_id=D, colour="red", team="away", significance=0.4)
    log.add(CardEvent, player_id=D, colour="yellow", team="away", significance=0.4)
    kinds = [moment.kind for moment in key_moments(log.events)]
    assert kinds == ["goal", "card"]


def test_summary_maps__a_real_match_has_consistent_maps() -> None:
    result = context_result()
    summary = result.summary
    shots = summary.team_stats_home.shots + summary.team_stats_away.shots
    assert len(summary.shot_map) == shots
    assert sum(link.count for link in summary.pass_matrix) <= summary.team_stats_home.passes + (
        summary.team_stats_away.passes
    )
    completed = sum(link.count for link in summary.pass_matrix)
    assert sum(flow.count for flow in summary.zone_pass_flow) == completed
    assert summary.xg_timeline[-1].home == pytest.approx(summary.team_stats_home.xg, abs=1e-3)
    assert len(summary.momentum_timeline) == summary.duration_s // 60 + 1
