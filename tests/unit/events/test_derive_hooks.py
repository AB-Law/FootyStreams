from footystreams.domain.types import PlayerId
from footystreams.events.derive.hooks import narrative_hooks
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.summary import PlayerMatchStats, TeamStats
from footystreams.events.summary_rows import Hook
from tests.factories.log_builder import LogBuilder

HOME9, AWAY9 = "plr_home0009", "plr_away0009"
EMPTY = (TeamStats(), TeamStats())


def _goal(
    log: LogBuilder, team: str, minute: int, scorer: str | None = None, period: int = 2
) -> str:
    event = log.add(
        GoalEvent,
        team=team,
        scorer_id=scorer or (HOME9 if team == "home" else AWAY9),
        minute=minute,
        period=period,
    )
    return event.id


def _kinds(hooks: tuple[Hook, ...]) -> list[str]:
    return [hook.kind for hook in hooks]


def test_hooks__a_late_goal_that_wins_it_is_a_late_winner() -> None:
    log = LogBuilder()
    _goal(log, "home", 20, period=1)
    _goal(log, "away", 60)
    decisive = _goal(log, "home", 89)
    hooks = narrative_hooks(log.events, [], EMPTY, is_derby=False)
    late = next(hook for hook in hooks if hook.kind == "late_winner")
    assert late.event_ids == (decisive,)
    assert late.text_key == "hook.late_winner"
    assert 0.0 < late.magnitude <= 1.0


def test_hooks__an_early_winner_is_not_late() -> None:
    log = LogBuilder()
    _goal(log, "home", 10, period=1)
    assert narrative_hooks(log.events, [], EMPTY, is_derby=False) == ()


def test_hooks__winning_after_trailing_is_a_comeback_sized_by_the_deficit() -> None:
    log = LogBuilder()
    _goal(log, "away", 10, period=1)
    _goal(log, "away", 30, period=1)
    _goal(log, "home", 50)
    _goal(log, "home", 60)
    decisive = _goal(log, "home", 70)
    comeback = next(
        hook
        for hook in narrative_hooks(log.events, [], EMPTY, is_derby=False)
        if hook.kind == "comeback"
    )
    assert comeback.magnitude == 2.0
    assert comeback.event_ids == (decisive,)


def test_hooks__a_draw_has_no_winner_stories() -> None:
    log = LogBuilder()
    _goal(log, "home", 85)
    _goal(log, "away", 88)
    assert narrative_hooks(log.events, [], EMPTY, is_derby=False) == ()


def test_hooks__three_goals_by_one_player_is_a_hat_trick() -> None:
    log = LogBuilder()
    ids = [_goal(log, "home", minute, HOME9, period=1) for minute in (5, 15, 25)]
    hooks = narrative_hooks(log.events, [], EMPTY, is_derby=False)
    hat = next(hook for hook in hooks if hook.kind == "hat_trick")
    assert hat.event_ids == tuple(ids)
    assert hat.magnitude == 3.0


def test_hooks__an_early_red_card_for_the_losing_side_is_a_turning_point() -> None:
    log = LogBuilder()
    red = log.add(CardEvent, team="away", player_id=AWAY9, colour="red", minute=30, period=1)
    _goal(log, "home", 60)
    hooks = narrative_hooks(log.events, [], EMPTY, is_derby=False)
    assert [hook.event_ids for hook in hooks if hook.kind == "red_card_turning_point"] == [
        (red.id,)
    ]


def test_hooks__a_red_card_for_the_winners_is_not_a_turning_point() -> None:
    log = LogBuilder()
    log.add(CardEvent, team="home", player_id=HOME9, colour="red", minute=30, period=1)
    _goal(log, "home", 60)
    assert "red_card_turning_point" not in _kinds(
        narrative_hooks(log.events, [], EMPTY, is_derby=False)
    )


def test_hooks__a_busy_keeper_who_barely_conceded_has_heroics() -> None:
    rows = [PlayerMatchStats(player_id=PlayerId("plr_home0001"), saves=7, goals_conceded=1)]
    hooks = narrative_hooks([], rows, EMPTY, is_derby=False)
    assert _kinds(hooks) == ["goalkeeper_heroics"]
    beaten = [PlayerMatchStats(player_id=PlayerId("plr_home0001"), saves=7, goals_conceded=3)]
    assert narrative_hooks([], beaten, EMPTY, is_derby=False) == ()


def test_hooks__a_side_with_twice_the_xg_that_did_not_win_was_dominant_unrewarded() -> None:
    teams = (TeamStats(xg=3.1), TeamStats(xg=0.9))
    hooks = narrative_hooks([], [], teams, is_derby=False)
    assert _kinds(hooks) == ["dominant_unrewarded"]
    assert hooks[0].magnitude == 2.2


def test_hooks__a_derby_is_always_a_story() -> None:
    assert _kinds(narrative_hooks([], [], EMPTY, is_derby=True)) == ["derby_result"]
