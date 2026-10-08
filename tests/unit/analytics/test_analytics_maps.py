import pytest

from footystreams.analytics.heatmap import frame_heatmap, touch_heatmap
from footystreams.analytics.maps import (
    pass_network,
    shot_locations,
    xa_totals,
    xg_totals,
    xt_totals,
    zone_flow,
)
from footystreams.domain.types import PlayerId
from footystreams.events.open_play import PassEvent, ShotEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from tests.factories.log_builder import LogBuilder
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import context_result

A, B = "plr_home0004", "plr_home0005"


def test_analytics__the_maps_equal_the_ones_in_the_summary() -> None:
    result = context_result()
    played = result.events[:-1]
    assert pass_network(played) == result.summary.pass_matrix
    assert zone_flow(played) == result.summary.zone_pass_flow
    assert shot_locations(played) == result.summary.shot_map


def test_analytics__totals_equal_the_summarys_team_and_player_numbers() -> None:
    result = context_result()
    played = result.events[:-1]
    summary = result.summary
    totals = xg_totals(played)
    assert totals["home"] == pytest.approx(summary.team_stats_home.xg, abs=1e-3)
    assert totals["away"] == pytest.approx(summary.team_stats_away.xg, abs=1e-3)
    xa, xt = xa_totals(played), xt_totals(played)
    for row in summary.player_stats:
        assert xa.get(row.player_id, 0.0) == pytest.approx(row.xa, abs=1e-3)
        assert xt.get(row.player_id, 0.0) == pytest.approx(row.xt, abs=1e-3)


def test_xg_totals__are_zero_for_a_log_without_shots() -> None:
    assert xg_totals([]) == {"home": 0.0, "away": 0.0}


def test_xa_and_xt__credit_the_assister_and_the_passer() -> None:
    log = LogBuilder()
    log.add(ShotEvent, player_id=B, xg=0.3, assist_id=A)
    log.add(PassEvent, from_player_id=A, to_player_id=B, xt_gain=0.02)
    log.add(PassEvent, from_player_id=A, to_player_id=B, xt_gain=0.5, outcome="incomplete")
    assert xa_totals(log.events) == {A: 0.3}
    assert xt_totals(log.events) == {A: 0.02}


def test_frame_heatmap__counts_one_cell_per_player_per_frame() -> None:
    config = merge_config(SimConfig(), {"emit_frames": True, "frame_interval_s": 30})
    setup = make_demo_setup()
    events = run_match(setup, 2, config, default_tables()).events
    frames = sum(e.type == "frame" for e in events)
    squad = frozenset(slot.player_id for slot in setup.home.lineup)
    grid = frame_heatmap(events, squad)
    assert len(grid) == 8
    assert all(len(row) == 12 for row in grid)
    assert sum(map(sum, grid)) <= frames * 11
    assert sum(map(sum, grid)) > frames * 9  # substitutes and sent-off players thin it slightly


def test_touch_heatmap__counts_the_events_a_player_took_part_in_by_cell() -> None:
    log = LogBuilder()
    for x, actor in ((0.05, A), (0.06, A), (0.95, A), (0.5, B)):
        log.add(
            PassEvent,
            from_player_id=actor,
            pos={"x": x, "y": 0.5},
            participants=[{"player_id": actor, "role": "actor"}],
        )
    grid = touch_heatmap(log.events, PlayerId(A))
    assert grid[4][0] == 2
    assert grid[4][11] == 1
    assert sum(map(sum, grid)) == 3
