from footystreams.analytics.annotate import annotate
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import GoalEvent, PassEvent
from footystreams.events.structure import FrameEvent
from tests.factories.log_builder import LogBuilder
from tests.helpers.logs import context_result

HOME9, AWAY9 = "plr_home0009", "plr_away0009"


def _goal(log: LogBuilder, team: str, minute: int, period: int = 2) -> str:
    scorer = HOME9 if team == "home" else AWAY9
    return log.add(GoalEvent, team=team, scorer_id=scorer, minute=minute, period=period).id


def test_annotate__a_late_winner_is_the_winning_goal_and_a_turning_point() -> None:
    log = LogBuilder()
    _goal(log, "home", 20, period=1)
    _goal(log, "away", 60)
    winner = _goal(log, "home", 88)
    annotations = {a.event_id: a for a in annotate(log.events)}
    assert annotations[winner].is_winning_goal
    assert annotations[winner].is_late_winner
    assert annotations[winner].was_turning_point
    assert not annotations[winner].comeback_completed
    assert annotations[winner].goal_of_the_match


def test_annotate__a_comeback_winner_is_marked() -> None:
    log = LogBuilder()
    _goal(log, "away", 10, period=1)
    _goal(log, "home", 50)
    winner = _goal(log, "home", 70)
    annotations = {a.event_id: a for a in annotate(log.events)}
    assert annotations[winner].comeback_completed
    assert not annotations[winner].is_late_winner


def test_annotate__a_draw_has_no_winning_goal() -> None:
    log = LogBuilder()
    _goal(log, "home", 20, period=1)
    _goal(log, "away", 70)
    assert not any(a.is_winning_goal for a in annotate(log.events))


def test_annotate__only_one_goal_of_the_match_and_none_without_goals() -> None:
    log = LogBuilder()
    for minute in (10, 20, 30):
        _goal(log, "home", minute, period=1)
    assert sum(a.goal_of_the_match for a in annotate(log.events)) == 1
    empty = LogBuilder()
    empty.add(PassEvent, from_player_id=HOME9)
    assert not any(a.goal_of_the_match for a in annotate(empty.events))


def test_annotate__an_early_red_for_the_side_that_lost_is_a_turning_point() -> None:
    log = LogBuilder()
    red = log.add(CardEvent, team="away", player_id=AWAY9, colour="red", minute=25, period=1).id
    _goal(log, "home", 60)
    annotations = {a.event_id: a for a in annotate(log.events)}
    assert annotations[red].was_turning_point


def test_annotate__frames_get_no_annotation_and_weights_are_bounded() -> None:
    log = LogBuilder()
    log.add(FrameEvent, ball_pos_x=0.5, ball_pos_y=0.5)
    _goal(log, "home", 89)
    annotations = annotate(log.events)
    assert len(annotations) == 1
    assert 0.0 <= annotations[0].narrative_weight <= 1.0


def test_annotate__a_real_match_has_at_most_one_winning_goal_and_one_per_event() -> None:
    events = context_result().events[:-1]
    annotations = annotate(events)
    assert [a.event_id for a in annotations] == [e.id for e in events]
    assert sum(a.is_winning_goal for a in annotations) <= 1
