from typing import Any

import pytest

from footystreams.events.context import ContextTag
from footystreams.events.derive.context import ContextTracker
from footystreams.events.discipline import CardEvent, InjuryEvent
from footystreams.events.open_play import GoalEvent, PassEvent, SaveEvent, ShotEvent
from footystreams.events.restarts import PenaltyEvent
from footystreams.events.structure import FrameEvent
from footystreams.events.types import MatchEvent
from tests.factories.log_builder import LogBuilder

HOME_SCORER = "plr_home0009"
AWAY_SCORER = "plr_away0009"


def _replay(events: list[MatchEvent], *, is_derby: bool = False) -> list[MatchEvent]:
    tracker = ContextTracker(is_derby=is_derby)
    return [tracker.annotate(event) for event in events]


def _goal(log: LogBuilder, team: str, scorer: str | None = None, **where: Any) -> MatchEvent:
    return log.add(
        GoalEvent,
        team=team,
        scorer_id=scorer or (HOME_SCORER if team == "home" else AWAY_SCORER),
        **where,
    )


def _tags_of_last(log: LogBuilder, *, is_derby: bool = False) -> set[ContextTag]:
    return set(_replay(log.events, is_derby=is_derby)[-1].ctx.tags)


@pytest.mark.parametrize(
    ("period", "minute", "stoppage", "expected", "absent"),
    [
        (1, 30, 0, set(), {ContextTag.LATE_GAME, ContextTag.STOPPAGE_TIME}),
        (1, 45, 2, {ContextTag.STOPPAGE_TIME}, {ContextTag.LAST_MINUTES, ContextTag.LATE_GAME}),
        (2, 74, 0, set(), {ContextTag.LATE_GAME}),
        (2, 75, 0, {ContextTag.LATE_GAME}, {ContextTag.LAST_MINUTES}),
        (2, 88, 0, {ContextTag.LATE_GAME, ContextTag.LAST_MINUTES}, set()),
        (2, 90, 1, {ContextTag.STOPPAGE_TIME, ContextTag.LAST_MINUTES}, set()),
    ],
)
def test_tags__time_tags_follow_the_clock(
    period: int, minute: int, stoppage: int, expected: set[ContextTag], absent: set[ContextTag]
) -> None:
    log = LogBuilder()
    log.add(PassEvent, from_player_id=HOME_SCORER, period=period, minute=minute, stoppage=stoppage)
    tags = _tags_of_last(log)
    assert expected <= tags
    assert not absent & tags


def test_tags__a_derby_is_tagged_on_every_event() -> None:
    log = LogBuilder()
    log.add(PassEvent, from_player_id=HOME_SCORER)
    assert ContextTag.DERBY in _tags_of_last(log, is_derby=True)
    assert ContextTag.DERBY not in _tags_of_last(log)


def test_tags__the_first_goal_is_the_opening_goal_and_the_next_equalises() -> None:
    log = LogBuilder()
    first = _goal(log, "home")
    equaliser = _goal(log, "away")
    tags = {event.id: set(event.ctx.tags) for event in _replay(log.events)}
    assert ContextTag.OPENING_GOAL in tags[first.id]
    assert ContextTag.EQUALISER in tags[equaliser.id]
    assert ContextTag.OPENING_GOAL not in tags[equaliser.id]


def test_tags__taking_the_lead_extending_it_and_a_consolation() -> None:
    log = LogBuilder()
    _goal(log, "home")
    _goal(log, "away")
    go_ahead = _goal(log, "home")
    extends = _goal(log, "home")
    consolation = _goal(log, "away")
    tags = {event.id: set(event.ctx.tags) for event in _replay(log.events)}
    assert ContextTag.GO_AHEAD_GOAL in tags[go_ahead.id]
    assert ContextTag.EXTENDS_LEAD in tags[extends.id]
    assert ContextTag.CONSOLATION_GOAL in tags[consolation.id]  # 3-2: still behind
    assert ContextTag.EQUALISER not in tags[extends.id]


def test_tags__a_goal_that_leaves_the_scorer_behind_is_a_consolation() -> None:
    log = LogBuilder()
    for _ in range(3):
        _goal(log, "home")
    consolation = _goal(log, "away")
    assert ContextTag.CONSOLATION_GOAL in set(_replay(log.events)[consolation.seq].ctx.tags)


def test_tags__scoring_after_being_behind_is_a_comeback_goal() -> None:
    log = LogBuilder()
    _goal(log, "home")
    _goal(log, "home")
    _goal(log, "away")
    comeback = _goal(log, "away")
    tags = {event.id: set(event.ctx.tags) for event in _replay(log.events)}
    assert ContextTag.COMEBACK_GOAL in tags[comeback.id]
    assert ContextTag.COMEBACK_GOAL not in tags[log.events[0].id]


def test_tags__a_second_and_third_goal_by_one_player_are_a_brace_and_a_hat_trick() -> None:
    log = LogBuilder()
    for _ in range(3):
        _goal(log, "home", HOME_SCORER)
    tags = [set(event.ctx.tags) for event in _replay(log.events)]
    assert ContextTag.BRACE not in tags[0]
    assert ContextTag.BRACE in tags[1]
    assert ContextTag.HAT_TRICK in tags[2]


def test_tags__a_goal_from_a_penalty_and_an_own_goal() -> None:
    log = LogBuilder()
    penalty = log.add(PenaltyEvent, taker_id=HOME_SCORER, outcome="goal")
    goal = log.add(GoalEvent, scorer_id=HOME_SCORER, caused_by=penalty.id)
    own = log.add(GoalEvent, team="away", scorer_id=HOME_SCORER, own_goal=True)
    tags = {event.id: set(event.ctx.tags) for event in _replay(log.events)}
    assert ContextTag.PENALTY in tags[goal.id]
    assert ContextTag.OWN_GOAL in tags[own.id]
    assert ContextTag.PENALTY not in tags[own.id]


def test_tags__men_advantage_goes_to_the_side_with_more_men() -> None:
    log = LogBuilder()
    home = log.add(PassEvent, from_player_id=HOME_SCORER, team="home", men=(11, 10))
    away = log.add(PassEvent, from_player_id=AWAY_SCORER, team="away", men=(11, 10))
    tags = {event.id: set(event.ctx.tags) for event in _replay(log.events)}
    assert ContextTag.MAN_ADVANTAGE in tags[home.id]
    assert ContextTag.TEN_MEN in tags[away.id]


def test_tags__chances_saves_woodwork_cards_and_injuries() -> None:
    log = LogBuilder()
    big = log.add(ShotEvent, player_id=HOME_SCORER, xg=0.45, outcome="saved")
    save = log.add(SaveEvent, team="away", keeper_id=AWAY_SCORER, shot_event_id=big.id)
    post = log.add(ShotEvent, player_id=HOME_SCORER, xg=0.05, outcome="woodwork")
    card = log.add(CardEvent, player_id=AWAY_SCORER, colour="second_yellow", team="away")
    injury = log.add(
        InjuryEvent, player_id=HOME_SCORER, apparent_severity="looks_serious", can_continue=False
    )
    tags = {event.id: set(event.ctx.tags) for event in _replay(log.events)}
    assert ContextTag.BIG_CHANCE in tags[big.id]
    assert ContextTag.BIG_SAVE in tags[save.id]
    assert ContextTag.WOODWORK in tags[post.id]
    assert ContextTag.BIG_CHANCE not in tags[post.id]
    assert ContextTag.SECOND_YELLOW in tags[card.id]
    assert ContextTag.INJURY_SCARE in tags[injury.id]


def test_momentum__shots_push_it_toward_the_shooting_side_and_it_fades() -> None:
    log = LogBuilder()
    log.add(ShotEvent, player_id=HOME_SCORER, xg=0.4, outcome="saved", second=0)
    log.add(PassEvent, from_player_id=HOME_SCORER, second=1)
    log.add(PassEvent, from_player_id=HOME_SCORER, minute=30)
    after, _, later = (event.ctx.momentum for event in _replay(log.events))
    assert after == 0.0  # causal: the shot's own credit is not in its own context
    assert _replay(log.events)[1].ctx.momentum > 0.2
    assert later == 0.0


def test_momentum__an_away_shot_pushes_it_negative() -> None:
    log = LogBuilder()
    log.add(ShotEvent, team="away", player_id=AWAY_SCORER, xg=0.4, outcome="saved")
    log.add(PassEvent, team="away", from_player_id=AWAY_SCORER, second=1)
    assert _replay(log.events)[1].ctx.momentum < -0.2


def test_intensity__a_busy_spell_is_hotter_than_a_quiet_one() -> None:
    quiet = LogBuilder()
    quiet.add(PassEvent, from_player_id=HOME_SCORER)
    busy = LogBuilder()
    for second in range(10):
        busy.add(ShotEvent, player_id=HOME_SCORER, xg=0.1, outcome="blocked", second=second)
    busy.add(PassEvent, from_player_id=HOME_SCORER, second=11)
    assert _replay(busy.events)[-1].ctx.intensity > _replay(quiet.events)[-1].ctx.intensity


def test_significance__a_late_chance_matters_more_than_an_early_one() -> None:
    early = LogBuilder()
    early.add(ShotEvent, player_id=HOME_SCORER, xg=0.2, outcome="saved", minute=10)
    late = LogBuilder()
    late.add(ShotEvent, player_id=HOME_SCORER, xg=0.2, outcome="saved", period=2, minute=89)
    assert _replay(late.events)[0].ctx.significance > _replay(early.events)[0].ctx.significance


def test_significance__a_pass_keeps_its_small_base_whatever_the_minute() -> None:
    log = LogBuilder()
    log.add(PassEvent, from_player_id=HOME_SCORER, period=2, minute=89)
    assert _replay(log.events)[0].ctx.significance == 0.04


def test_annotate__the_context_of_an_event_ignores_everything_after_it() -> None:
    log = LogBuilder()
    for minute in (10, 30, 50):
        log.add(ShotEvent, player_id=HOME_SCORER, xg=0.2, outcome="saved", minute=minute)
        _goal(log, "home", minute=minute, second=5)
    full = _replay(log.events)
    for cut in range(1, len(log.events) + 1):
        prefix = _replay(log.events[:cut])
        assert prefix[-1].ctx == full[cut - 1].ctx


def test_annotate__frames_are_passed_through_and_leave_the_history_alone() -> None:
    log = LogBuilder()
    log.add(ShotEvent, player_id=HOME_SCORER, xg=0.4, outcome="saved")
    frame = log.add(FrameEvent, ball_pos_x=0.5, ball_pos_y=0.5)
    log.add(PassEvent, from_player_id=HOME_SCORER, second=1)
    tracker = ContextTracker()
    out = [tracker.annotate(event) for event in log.events]
    assert out[1] is frame
    without = ContextTracker()
    plain = [without.annotate(event) for event in log.events if event is not frame]
    assert out[2].ctx == plain[1].ctx
