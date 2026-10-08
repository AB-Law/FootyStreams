import pytest

from footystreams.events.derive.summary import SummaryInputs, build_summary
from footystreams.events.discipline import CardEvent, FoulEvent, SubstitutionEvent
from footystreams.events.open_play import (
    ClearanceEvent,
    DribbleEvent,
    GoalEvent,
    InterceptionEvent,
    OffsideEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.restarts import CornerEvent
from footystreams.events.summary import MatchSummary, PlayerMatchStats
from tests.factories.log_builder import LogBuilder
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import context_result

SETUP = make_demo_setup()
HOME = [slot.player_id for slot in SETUP.home.lineup]
AWAY = [slot.player_id for slot in SETUP.away.lineup]
HOME_BENCH = list(SETUP.home.bench)
INPUTS = SummaryInputs(seed=1, config_hash="cfg", log_digest="digest")


def _summary(log: LogBuilder) -> MatchSummary:
    return build_summary(log.events, SETUP, INPUTS)


def _row(summary: MatchSummary, player_id: str) -> PlayerMatchStats:
    return next(row for row in summary.player_stats if row.player_id == player_id)


def test_shots__count_target_xg_big_chances_and_the_key_pass_behind_them() -> None:
    log = LogBuilder()
    log.add(ShotEvent, player_id=HOME[9], xg=0.4, outcome="saved", assist_id=HOME[8])
    log.add(ShotEvent, player_id=HOME[9], xg=0.1, outcome="off_target")
    summary = _summary(log)
    assert summary.team_stats_home.shots == 2
    assert summary.team_stats_home.shots_on_target == 1
    assert summary.team_stats_home.xg == pytest.approx(0.5)
    assert summary.team_stats_home.big_chances == 1
    assert summary.team_stats_home.key_passes == 1
    assert _row(summary, HOME[9]).shots_on_target == 1
    assert _row(summary, HOME[8]).key_passes == 1
    assert _row(summary, HOME[8]).xa == pytest.approx(0.4)


def test_goals__credit_the_scorer_assister_and_the_keeper_who_conceded() -> None:
    log = LogBuilder()
    log.add(GoalEvent, scorer_id=HOME[9], assist_id=HOME[8])
    log.add(GoalEvent, team="away", scorer_id=AWAY[9], own_goal=False)
    summary = _summary(log)
    assert (summary.score_home, summary.score_away) == (1, 1)
    assert _row(summary, HOME[9]).goals == 1
    assert _row(summary, HOME[8]).assists == 1
    assert _row(summary, HOME[0]).goals_conceded == 1
    assert _row(summary, AWAY[0]).goals_conceded == 1


def test_goals__an_own_goal_counts_for_the_score_but_not_the_scorers_tally() -> None:
    log = LogBuilder()
    log.add(GoalEvent, team="home", scorer_id=AWAY[3], own_goal=True)
    summary = _summary(log)
    assert summary.score_home == 1
    assert _row(summary, AWAY[3]).goals == 0
    assert _row(summary, AWAY[0]).goals_conceded == 1


def test_goals__a_replacement_keeper_is_credited_after_the_change() -> None:
    log = LogBuilder()
    log.add(
        SubstitutionEvent,
        team="away",
        player_off_id=AWAY[0],
        player_on_id=SETUP.away.bench[0],
        minute=50,
    )
    log.add(GoalEvent, scorer_id=HOME[9], minute=60)
    summary = _summary(log)
    assert _row(summary, AWAY[0]).goals_conceded == 0
    assert _row(summary, SETUP.away.bench[0]).goals_conceded == 1


def test_passes__accuracy_threat_progressive_and_field_tilt() -> None:
    log = LogBuilder()
    for end_x, outcome in ((0.9, "complete"), (0.3, "complete"), (0.8, "incomplete")):
        log.add(
            PassEvent,
            from_player_id=HOME[5],
            to_player_id=HOME[6],
            outcome=outcome,
            end_pos={"x": end_x, "y": 0.5},
            xt_gain=0.02,
            progressive=end_x > 0.5,
        )
    log.add(
        PassEvent,
        team="away",
        from_player_id=AWAY[5],
        to_player_id=AWAY[6],
        outcome="complete",
        end_pos={"x": 0.9, "y": 0.5},
        xt_gain=0.01,
    )
    summary = _summary(log)
    home = summary.team_stats_home
    assert home.passes == 3
    assert home.pass_accuracy == pytest.approx(2 / 3, abs=1e-4)
    assert home.xt == pytest.approx(0.04)
    assert _row(summary, HOME[5]).progressive_passes == 1
    assert home.field_tilt == pytest.approx(0.5)  # 1 final-third pass each (attack_dir +1 for both)
    assert _row(summary, HOME[5]).passes_completed == 2


def test_defending__tackles_interceptions_clearances_saves_offsides_and_fouls() -> None:
    log = LogBuilder()
    log.add(TackleEvent, player_id=HOME[3], target_id=AWAY[9], outcome="won")
    log.add(TackleEvent, player_id=HOME[3], target_id=AWAY[9], outcome="missed")
    log.add(TackleEvent, player_id=HOME[3], target_id=AWAY[9], outcome="foul")
    log.add(InterceptionEvent, player_id=HOME[4])
    log.add(ClearanceEvent, player_id=HOME[2])
    log.add(SaveEvent, keeper_id=HOME[0], shot_event_id="x")
    log.add(OffsideEvent, team="away", player_id=AWAY[9])
    log.add(FoulEvent, fouler_id=HOME[3], fouled_id=AWAY[9])
    log.add(CornerEvent, taker_id=HOME[7])
    log.add(DribbleEvent, player_id=HOME[8], outcome="success")
    log.add(DribbleEvent, player_id=HOME[8], outcome="lost")
    summary = _summary(log)
    home = summary.team_stats_home
    assert (home.tackles, home.tackles_won) == (2, 1)
    assert (home.interceptions, home.clearances, home.saves) == (1, 1, 1)
    assert (home.fouls, home.corners, home.dribbles, home.dribbles_won) == (1, 1, 2, 1)
    assert summary.team_stats_away.offsides == 1
    assert _row(summary, HOME[3]).fouls == 1
    assert _row(summary, AWAY[9]).fouled == 1
    assert _row(summary, HOME[0]).saves == 1


def test_cards__second_yellow_counts_as_a_yellow_and_a_red_and_ends_the_spell() -> None:
    log = LogBuilder()
    log.add(CardEvent, team="away", player_id=AWAY[4], colour="second_yellow", minute=70)
    summary = _summary(log)
    row = _row(summary, AWAY[4])
    assert (row.yellows, row.reds, row.minutes) == (1, 1, 70)
    assert summary.team_stats_away.reds == 1


def test_rows__substitutes_who_played_get_rows_with_their_minutes() -> None:
    log = LogBuilder()
    log.add(SubstitutionEvent, player_off_id=HOME[5], player_on_id=HOME_BENCH[1], minute=60)
    log.add(PassEvent, from_player_id=HOME[6], minute=89, second=59)
    summary = _summary(log)
    on = _row(summary, HOME_BENCH[1])
    assert (on.starts, on.minutes) == (False, 30)
    assert _row(summary, HOME[5]).minutes == 60
    assert HOME_BENCH[0] not in {row.player_id for row in summary.player_stats}


def test_rows__clean_sheets_need_an_unbeaten_side_and_an_hour_on_the_pitch() -> None:
    log = LogBuilder()
    log.add(CardEvent, player_id=HOME[4], colour="red", minute=30)
    log.add(PassEvent, from_player_id=HOME[6], minute=89, second=59)
    summary = _summary(log)
    assert _row(summary, HOME[3]).clean_sheet
    assert not _row(summary, HOME[4]).clean_sheet


def test_real_match__player_rows_add_up_to_the_team_rows() -> None:
    summary = context_result().summary
    home_ids = set(SETUP.home.squad)
    rows = [row for row in summary.player_stats if row.player_id in home_ids]
    home = summary.team_stats_home
    assert sum(row.shots for row in rows) == home.shots
    assert sum(row.passes for row in rows) == home.passes
    assert sum(row.tackles for row in rows) == home.tackles
    assert sum(row.interceptions for row in rows) == home.interceptions
    assert sum(row.clearances for row in rows) == home.clearances
    assert sum(row.saves for row in rows) == home.saves
    assert sum(row.fouls for row in rows) == home.fouls
    assert sum(row.key_passes for row in rows) == home.key_passes
    assert sum(row.dribbles_won for row in rows) == home.dribbles_won
    assert sum(row.xg for row in rows) == pytest.approx(home.xg, abs=1e-3)
    assert sum(row.yellows for row in rows) == home.yellows


def test_real_match__every_shooter_has_a_row() -> None:
    result = context_result()
    known = {row.player_id for row in result.summary.player_stats}
    shooters = {e.player_id for e in result.events if isinstance(e, ShotEvent)}
    assert shooters <= known
