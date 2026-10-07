import pytest

from footystreams.events.structure import AddedTimeEvent, HalftimeEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.sim.config import StoppageConfig
from footystreams.sim.stoppage import added_minutes
from tests.factories.referee import make_referee
from tests.factories.sim_teams import make_demo_setup

CFG = StoppageConfig()


def test_added_minutes__grows_with_stoppage_and_with_referee_generosity() -> None:
    assert added_minutes(60.0, 0.5, 1, CFG) < added_minutes(400.0, 0.5, 1, CFG)
    assert added_minutes(300.0, 0.0, 1, CFG) <= added_minutes(300.0, 1.0, 1, CFG)


def test_added_minutes__is_clamped_per_half() -> None:
    assert added_minutes(0.0, 0.5, 1, CFG) == CFG.first_half_min
    assert added_minutes(0.0, 0.5, 2, CFG) == CFG.second_half_min
    assert added_minutes(10_000.0, 1.0, 1, CFG) == CFG.first_half_max
    assert added_minutes(10_000.0, 1.0, 2, CFG) == CFG.second_half_max


def test_added_minutes__rounds_up() -> None:
    # 100 s of stoppage x 0.65 x 1.0 = 1.08 minutes -> 2
    assert added_minutes(100.0, 0.5, 2, CFG) == 2


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_run_match__with_added_time_each_half_announces_it_and_plays_it(seed: int) -> None:
    result = run_match(make_demo_setup(), seed, SimConfig(), default_tables(), make_referee())
    announcements = [e for e in result.events if isinstance(e, AddedTimeEvent)]
    assert [e.clock.period for e in announcements] == [1, 2]
    halftime = next(e for e in result.events if isinstance(e, HalftimeEvent))
    assert halftime.clock.stoppage >= announcements[0].minutes
    assert result.summary.duration_s > 5400


def test_run_match__without_added_time_there_is_no_announcement() -> None:
    cfg = merge_config(SimConfig(), {"stoppage": {"enabled": False}})
    result = run_match(make_demo_setup(), 1, cfg, default_tables())
    assert not any(isinstance(e, AddedTimeEvent) for e in result.events)
