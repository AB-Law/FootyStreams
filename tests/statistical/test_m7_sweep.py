"""M7 sweeps: summaries recompute, ratings stay in range, context is causal and frames inert."""

from collections import Counter

import pytest

from footystreams.events.derive.context import ContextTracker
from footystreams.events.open_play import ShotEvent
from footystreams.events.structure import FrameEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.verify import verify_match
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import without_frames_renumbered

pytestmark = [pytest.mark.slow, pytest.mark.statistical, pytest.mark.timeout(1800)]

TABLES = default_tables()
FORMATIONS = sorted(TABLES.formations)
MATCHES = 150


def _setup(index: int):  # type: ignore[no-untyped-def]
    return make_demo_setup(
        home_strength=54 + (index * 7) % 17,
        away_strength=54 + (index * 11) % 17,
        home_formation=FORMATIONS[index % 8],
        away_formation=FORMATIONS[(index * 3 + 1) % 8],
        match_id=f"mch_sweep{index:04d}",
    )


def test_sweep__every_summary_recomputes_and_rows_add_up() -> None:
    hooks: Counter[str] = Counter()
    for index in range(MATCHES):
        setup = _setup(index)
        result = run_match(setup, 1500 + index, SimConfig(), TABLES)
        assert verify_match(result.events, setup) == []
        summary = result.summary
        assert all(3.0 <= rating.rating <= 10.0 for rating in summary.ratings)
        best = max(rating.rating for rating in summary.ratings)
        assert (
            next(r for r in summary.ratings if r.player_id == summary.player_of_the_match).rating
            == best
        )
        home_ids = set(setup.home.squad)
        rows = [row for row in summary.player_stats if row.player_id in home_ids]
        assert sum(row.shots for row in rows) == summary.team_stats_home.shots
        assert sum(row.passes for row in rows) == summary.team_stats_home.passes
        assert sum(row.goals for row in rows) <= summary.score_home
        hooks.update(hook.kind for hook in summary.hooks)
    assert hooks["late_winner"] + hooks["comeback"] > 0


def test_sweep__momentum_leans_toward_the_side_that_is_shooting() -> None:
    home_total = away_total = 0.0
    home_shots = away_shots = 0
    for index in range(60):
        result = run_match(_setup(index), 2500 + index, SimConfig(), TABLES)
        for event in result.events:
            if isinstance(event, ShotEvent):
                if event.team == "home":
                    home_total, home_shots = home_total + event.ctx.momentum, home_shots + 1
                else:
                    away_total, away_shots = away_total + event.ctx.momentum, away_shots + 1
    assert home_total / home_shots > away_total / away_shots + 0.1


def test_sweep__frames_change_no_other_event_across_setups() -> None:
    with_frames = merge_config(SimConfig(), {"emit_frames": True, "frame_interval_s": 10})
    for index in range(12):
        setup = _setup(index)
        off = run_match(setup, 3500 + index, SimConfig(), TABLES)
        on = run_match(setup, 3500 + index, with_frames, TABLES)
        assert without_frames_renumbered(on.events) == without_frames_renumbered(off.events)
        assert verify_match(on.events, setup) == []
        assert any(isinstance(e, FrameEvent) for e in on.events)
        assert on.summary.team_stats_home == off.summary.team_stats_home


def test_sweep__the_context_of_any_prefix_of_the_log_matches_the_full_run() -> None:
    for index in range(10):
        setup = _setup(index)
        events = run_match(setup, 4500 + index, SimConfig(), TABLES).events[:-1]
        for cut in (len(events) // 4, len(events) // 2, len(events) - 1):
            tracker = ContextTracker(is_derby=setup.is_derby)
            replayed = [tracker.annotate(event) for event in events[:cut]]
            assert [event.ctx for event in replayed] == [event.ctx for event in events[:cut]]
