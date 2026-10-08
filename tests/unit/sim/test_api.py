import hashlib

import pytest

from footystreams.events.digest import log_digest
from footystreams.events.open_play import GoalEvent
from footystreams.events.structure import FulltimeEvent, HalftimeEvent, KickoffEvent
from footystreams.events.summary import MatchSummaryEvent
from footystreams.sim import (
    EngineError,
    InvalidSetupError,
    SimConfig,
    default_tables,
    engine,
    run_match,
    simulate_match,
)
from footystreams.sim.config import OffsideConfig, PositionConfig, config_hash
from footystreams.sim.positioning import update_positions
from footystreams.sim.state import MatchState
from tests.factories.match import make_setup, make_team_sheet
from tests.factories.referee import make_referee
from tests.factories.sim_teams import DEMO_REFEREE_ID, make_demo_setup

TABLES = default_tables()
CFG = SimConfig()
SETUP = make_demo_setup()


def _digest_of(seed: int) -> str:
    return run_match(SETUP, seed, CFG, TABLES).log_digest


def test_run_match__same_inputs_give_byte_identical_logs() -> None:
    first = run_match(SETUP, 7, CFG, TABLES)
    second = run_match(SETUP, 7, CFG, TABLES)
    first_bytes = "\n".join(event.model_dump_json() for event in first.events)
    second_bytes = "\n".join(event.model_dump_json() for event in second.events)
    assert first_bytes == second_bytes
    assert first.log_digest == second.log_digest


def test_run_match__different_seeds_give_different_logs() -> None:
    assert _digest_of(1) != _digest_of(2)


def test_run_match__different_config_changes_the_hash_and_usually_the_log() -> None:
    other = SimConfig(home_advantage_scale=0.5)
    result = run_match(SETUP, 1, other, TABLES)
    assert result.config_hash == config_hash(other) != config_hash(CFG)


def test_run_match__structure_kickoff_halftime_second_kickoff_fulltime_summary() -> None:
    events = run_match(SETUP, 3, CFG, TABLES).events
    types = [event.type for event in events]
    assert types[0] == "kickoff"
    assert types[-2:] == ["fulltime", "match_summary"]
    assert types.count("halftime") == 1
    assert types.count("kickoff") == 2
    kickoffs = [e for e in events if isinstance(e, KickoffEvent)]
    assert [k.period for k in kickoffs] == [1, 2]


def test_run_match__score_in_context_and_summary_equals_the_goal_events() -> None:
    result = run_match(SETUP, 11, CFG, TABLES)
    goals = [e for e in result.events if isinstance(e, GoalEvent)]
    home = sum(g.team == "home" for g in goals)
    away = sum(g.team == "away" for g in goals)
    fulltime = next(e for e in result.events if isinstance(e, FulltimeEvent))
    halftime = next(e for e in result.events if isinstance(e, HalftimeEvent))
    assert (fulltime.score_home, fulltime.score_away) == (home, away)
    assert (result.summary.score_home, result.summary.score_away) == (home, away)
    assert halftime.score_home <= home
    assert all(g.ctx.score_home + g.ctx.score_away >= 1 for g in goals)


def test_run_match__summary_digest_is_the_digest_of_all_prior_events() -> None:
    result = run_match(SETUP, 5, CFG, TABLES)
    assert isinstance(result.events[-1], MatchSummaryEvent)
    assert result.summary.log_digest == log_digest(result.events[:-1])
    assert len(result.summary.log_digest) == len(hashlib.sha256(b"").hexdigest())


def test_simulate_match__streams_the_same_events_as_run_match() -> None:
    streamed = tuple(simulate_match(SETUP, 9, CFG, TABLES))
    assert streamed == run_match(SETUP, 9, CFG, TABLES).events


def test_run_match__summary_team_stats_are_consistent_with_the_log() -> None:
    summary = run_match(SETUP, 4, CFG, TABLES).summary
    home, away = summary.team_stats_home, summary.team_stats_away
    assert home.possession + away.possession == pytest.approx(1.0, abs=0.01)
    assert 0 <= home.shots_on_target <= home.shots
    assert 0.0 <= home.pass_accuracy <= 1.0
    assert summary.duration_s >= 5400
    assert sum(row.starts for row in summary.player_stats) == 22
    assert len(summary.player_stats) >= 22
    assert sum(row.goals for row in summary.player_stats) == summary.score_home + summary.score_away


def test_run_match__setup_ref_carries_the_ids() -> None:
    result = run_match(SETUP, 1, CFG, TABLES)
    assert result.setup_ref.match_id == SETUP.match_id
    assert result.setup_ref.home_club_id == SETUP.home.club.id


def test_simulate_match__players_on_both_sheets__is_rejected_before_any_event() -> None:
    home = make_team_sheet(club_id="clb_home01", side="home")
    twin = make_setup(
        home=home, away=home.model_copy(update={"club": make_team_sheet(side="away").club})
    )
    with pytest.raises(InvalidSetupError, match="both sheets"):
        simulate_match(twin, 1, CFG, TABLES)


def test_simulate_match__referee_other_than_the_one_named__is_rejected() -> None:
    other = make_referee(id="ref_other001")
    with pytest.raises(InvalidSetupError, match="ref_other001"):
        simulate_match(SETUP, 1, CFG, TABLES, other)


def test_simulate_match__the_named_referee__is_accepted() -> None:
    named = make_referee(id=DEMO_REFEREE_ID)
    assert run_match(SETUP, 1, CFG, TABLES, named).events


def test_simulate_match__same_club_on_both_sides__is_rejected() -> None:
    away = make_team_sheet(club_id="clb_home01", side="away")
    with pytest.raises(InvalidSetupError, match="same club"):
        simulate_match(make_setup(away=away), 1, CFG, TABLES)


def test_run_match__stream_without_a_summary__raises_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truncated = run_match(SETUP, 1, CFG, TABLES).events[:-1]
    monkeypatch.setattr("footystreams.sim.api.simulate_match", lambda *_: iter(truncated))

    with pytest.raises(EngineError, match="without a summary"):
        run_match(SETUP, 1, CFG, TABLES)


def test_run_match__no_position_update_spans_a_goal_celebration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The clock runs through a celebration, but players stay in the kick-off formation.

    Dead balls and cards also stop the clock for a while, so only the first update after a goal
    is held to the celebration length.
    """
    after_goal: list[float] = []
    goals_seen = 0

    def spy(
        state: MatchState, dt: float, cfg: PositionConfig, offside: OffsideConfig | None
    ) -> None:
        nonlocal goals_seen
        goals = state.home.score + state.away.score
        if goals > goals_seen:
            after_goal.append(dt)
        goals_seen = goals
        update_positions(state, dt, cfg, offside)

    monkeypatch.setattr(engine, "update_positions", spy)

    result = run_match(SETUP, 7, CFG, TABLES)

    assert result.summary.score_home + result.summary.score_away > 0
    assert after_goal
    assert max(after_goal) < CFG.tempo.celebration_s - CFG.tempo.celebration_spread_s
