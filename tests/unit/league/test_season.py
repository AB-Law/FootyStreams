"""A whole season through the league: schedule, daily tick, matches, money and replay."""

from __future__ import annotations

import json

import pytest

from footystreams.domain.fixture import FixtureStatus
from footystreams.domain.match import MatchSetup
from footystreams.domain.mood import ModifierVisibility
from footystreams.league.clock import write_date
from footystreams.league.season import SeasonResult
from footystreams.persistence.ports import UnitOfWorkFactory
from tests.factories.league_run import (
    cached_season,
    cached_small_season,
    make_engine,
    make_runner,
    play_season,
    season_fingerprint,
)


def _small() -> tuple[SeasonResult, UnitOfWorkFactory]:
    return cached_small_season()


def test_run_season__every_fixture_is_played_exactly_once() -> None:
    result, factory = _small()
    with factory() as uow:
        fixtures = uow.fixtures.all()
        matches = uow.matches.all()
    assert len(fixtures) == len(matches) == 12
    assert {f.status for f in fixtures} == {FixtureStatus.PLAYED}
    assert result.matches_played == 12
    assert [row.played for row in result.table] == [6, 6, 6, 6]


def test_run_season__table_is_ordered_and_consistent_with_the_results() -> None:
    result, _ = _small()
    points = [row.points for row in result.table]
    assert points == sorted(points, reverse=True)
    assert [row.position for row in result.table] == [1, 2, 3, 4]
    assert sum(r.goals_for for r in result.table) == sum(r.goals_against for r in result.table)
    assert sum(r.won for r in result.table) == sum(r.lost for r in result.table)


def test_run_season__a_standings_snapshot_is_stored_after_every_matchday() -> None:
    result, factory = _small()
    with factory() as uow:
        snapshots = sorted(uow.standings.all(), key=lambda s: s.after_matchday)
    assert [s.after_matchday for s in snapshots] == list(range(1, 7))
    assert snapshots[-1].rows == result.table


def test_run_season__money_moves_and_prize_money_is_paid_at_the_end() -> None:
    _, factory = _small()
    with factory() as uow:
        memos = {e.memo_key for e in uow.ledger.all()}
    assert {
        "gate",
        "player_wages",
        "league_prize",
        "broadcast_merit",
        "sponsor_instalment",
    } <= memos


def test_run_season__state_stays_valid_and_memory_tables_stay_empty() -> None:
    _, factory = _small()
    with factory() as uow:
        assert uow.memories.count() == 0
        for player in uow.players.all():
            if player.current_injury:
                assert player.current_injury.expected_return_on > player.current_injury.started_on
            assert 0.0 <= player.fatigue <= 1.0
            assert 0.0 <= player.morale <= 1.0


def test_run_season__private_modifiers__never_appear_in_the_event_log() -> None:
    _, factory = _small()
    with factory() as uow:
        private = [m for m in uow.modifiers.all() if m.visibility is ModifierVisibility.PRIVATE]
        events = json.dumps([e.model_dump(mode="json") for e in uow.events.all()])
    assert private
    assert not any(m.id in events or m.summary_key in events for m in private)


@pytest.mark.timeout(120)
def test_run_season__same_seed_twice__identical_standings_and_ledger() -> None:
    first, factory_a = _small()
    second, factory_b = play_season(2, 4)
    assert first.table == second.table
    assert season_fingerprint(factory_a) == season_fingerprint(factory_b)


@pytest.mark.timeout(120)
def test_run_season__different_seed__different_season() -> None:
    _, factory_a = _small()
    _, factory_b = play_season(3, 4)
    assert season_fingerprint(factory_a) != season_fingerprint(factory_b)


def test_run_day__repeating_a_logged_day__changes_nothing() -> None:
    runner, factory = make_runner(2, 4)
    first = runner.run_day()
    with factory() as uow:
        before = uow.ledger.count(), uow.stage_log.count()
    with factory() as uow:  # wind the clock back one day and run the same day again
        write_date(uow, first.date)
        uow.commit()
    again = runner.run_day()
    with factory() as uow:
        after = uow.ledger.count(), uow.stage_log.count()
    assert first.stages_run
    assert again.stages_run == ()
    assert before == after


@pytest.mark.slow
@pytest.mark.timeout(240)
def test_run_season__eight_clubs__is_replayable_and_balanced() -> None:
    result, factory = cached_season(1)
    assert result.matches_played == 56
    assert {row.played for row in result.table} == {14}
    again, factory_again = play_season(1)
    assert result.table == again.table
    assert season_fingerprint(factory) == season_fingerprint(factory_again)


@pytest.mark.slow
@pytest.mark.timeout(240)
def test_run_season__sqlite_backend__gives_the_same_season_as_memory() -> None:
    memory, factory_memory = _small()
    sql, factory_sql = play_season(2, 4, backend="sql")
    assert sql.table == memory.table
    assert season_fingerprint(factory_sql) == season_fingerprint(factory_memory)


def test_replay__a_match_from_its_stored_sheets__reproduces_the_same_log() -> None:
    _, factory = _small()
    engine = make_engine(2)
    with factory() as uow:
        match = uow.matches.all()[3]
    setup = MatchSetup(
        match_id=match.id,
        fixture_id=match.fixture_id,
        home=match.home_sheet,
        away=match.away_sheet,
        weather=match.weather,
        referee_id=match.referee_id,
        attendance=match.attendance,
        is_derby=match.is_derby,
        importance=match.importance,
    )
    replayed = engine.simulator.simulate(setup, match.seed)
    assert replayed.log_digest == match.log_digest
    assert replayed.summary.score_home == match.home_goals
