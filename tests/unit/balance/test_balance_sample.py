from __future__ import annotations

from footystreams.balance.sample import MatchSample, sample_from
from footystreams.events.discipline import InjuryEvent, SubstitutionEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.restarts import PenaltyEvent
from footystreams.events.structure import AddedTimeEvent
from tests.factories.log_builder import LogBuilder
from tests.factories.result import make_match_result
from tests.factories.sim_teams import make_demo_setup

SETUP = make_demo_setup()
OFF = SETUP.home.lineup[3].player_id
ON = SETUP.home.bench[0]
SCORER = SETUP.home.lineup[9].player_id


def _sample(log: LogBuilder) -> MatchSample:
    result = make_match_result().model_copy(update={"events": tuple(log.events)})
    return sample_from(result, gap=2.5)


def _substitute(  # noqa: PLR0913 - the clock is described by these independent fields
    log: LogBuilder,
    reason: str,
    *,
    minute: int,
    period: int = 1,
    second: int = 0,
    stoppage: int = 0,
) -> None:
    log.add(
        SubstitutionEvent,
        player_off_id=OFF,
        player_on_id=ON,
        reason=reason,
        period=period,
        minute=minute,
        second=second,
        stoppage=stoppage,
    )


def test_sample_from__a_tactical_change_before_the_break_is_early() -> None:
    log = LogBuilder()
    _substitute(log, "fresh_legs", minute=30)

    assert _sample(log).early_tactical_subs == 1


def test_sample_from__half_time_and_injury_changes_are_not_early() -> None:
    log = LogBuilder()
    _substitute(log, "protect_lead", minute=45, second=2, stoppage=3)  # the half-time window
    _substitute(log, "injury", minute=20)
    _substitute(log, "chase_game", period=2, minute=60)

    assert _sample(log).early_tactical_subs == 0


def test_sample_from__counts_each_sides_changes_separately() -> None:
    log = LogBuilder()
    log.add(SubstitutionEvent, player_off_id=OFF, player_on_id=ON, team="home", period=2, minute=60)
    log.add(SubstitutionEvent, player_off_id=OFF, player_on_id=ON, team="away", period=2, minute=61)
    log.add(SubstitutionEvent, player_off_id=OFF, player_on_id=ON, team="away", period=2, minute=70)

    sample = _sample(log)

    assert (sample.home.substitutions, sample.away.substitutions) == (1, 2)


def test_sample_from__goal_timing_penalties_injuries_and_added_time() -> None:
    log = LogBuilder()
    log.add(GoalEvent, scorer_id=SCORER, period=1, minute=20)
    log.add(GoalEvent, scorer_id=SCORER, period=2, minute=50)
    log.add(GoalEvent, scorer_id=SCORER, period=2, minute=90, stoppage=2)
    log.add(PenaltyEvent, taker_id=SCORER, outcome="goal", period=2, minute=80)
    log.add(PenaltyEvent, taker_id=SCORER, outcome="saved", period=2, minute=85)
    log.add(InjuryEvent, player_id=OFF, period=2, minute=70)
    log.add(AddedTimeEvent, minutes=2, period=1, minute=45)
    log.add(AddedTimeEvent, minutes=5, period=2, minute=90)

    sample = _sample(log)

    assert (sample.goals_second_half, sample.goals_late) == (2, 1)
    assert (sample.penalties, sample.penalties_scored, sample.injuries) == (2, 1, 1)
    assert (sample.added_first_half, sample.added_second_half) == (2, 5)
    assert sample.gap == 2.5
