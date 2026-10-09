import pytest

from footystreams.events.discipline import CardEvent, SubstitutionEvent, TacticalChangeEvent
from footystreams.events.open_play import GoalEvent
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.sim.manager_ai import ManagerAI
from footystreams.sim.play import Play
from footystreams.sim.rng import SimRng
from footystreams.sim.tactics_view import mentality_name, shift_mentality
from tests.factories.sim_play import make_play
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import log_with
from tests.helpers.sim import assert_match_valid

DECISIVE = {
    "fatigue": {"enabled": True},
    "manager": {"enabled": True, "stay_weight": 1e-9},
}
LATE_S = 4500.0  # 75 minutes in


def _late_trailing_play(manager: dict[str, object] | None = None) -> tuple[Play, ManagerAI]:
    config = merge_config(SimConfig(), DECISIVE)
    config = merge_config(config, {"manager": manager or {}})
    play = make_play(seed=2, setup=make_demo_setup(), config=config)
    play.state.played_before_s = LATE_S
    play.state.away.score = 1
    return play, ManagerAI(play, SimRng(11), SimRng(12))


def _goal() -> MatchEvent:
    return next(e for e in log_with("goal") if isinstance(e, GoalEvent))


def _of_type(play: Play, kind: type) -> list[MatchEvent]:
    return [e for e in play.emit.events if isinstance(e, kind)]


def test_after_action__nothing_happens_without_events_or_a_stoppage() -> None:
    play, manager = _late_trailing_play()
    assert manager.after_action([]) == 0.0
    open_play = next(e for e in log_with("goal") if e.type == "pass")
    assert manager.after_action([open_play]) == 0.0
    assert not play.emit.events


def test_after_action__a_goal_at_a_stoppage_makes_a_trailing_side_react() -> None:
    play, manager = _late_trailing_play()
    seconds = manager.after_action([_goal()])
    assert seconds > 0.0
    assert _of_type(play, SubstitutionEvent)
    assert _of_type(play, TacticalChangeEvent)
    assert play.state.home.view.mentality > 0.0


def test_after_action__several_changes_at_one_stoppage_use_one_window() -> None:
    play, manager = _late_trailing_play()

    manager.after_action([_goal()])

    home = play.state.home
    assert home.subs_used > 1
    assert home.windows_used == 1


def test_after_action__a_manager_who_wants_more_changes_stops_at_the_limit() -> None:
    play, manager = _late_trailing_play({"max_subs": 1})

    manager.after_action([_goal()])

    assert play.state.home.subs_used == 1


def test_after_action__a_dismissal_triggers_a_review_too() -> None:
    play, manager = _late_trailing_play()
    card = next(e for e in log_with("red") if isinstance(e, CardEvent) and e.colour != "yellow")
    manager.after_action([card])
    assert play.emit.events


def test_after_action__a_booking_alone_does_not_trigger() -> None:
    play, manager = _late_trailing_play()
    yellow = next(e for e in log_with("yellow") if isinstance(e, CardEvent))
    assert manager.after_action([yellow]) == 0.0
    assert not play.emit.events


def test_after_action__mentality_waits_out_the_cooldown() -> None:
    play, manager = _late_trailing_play()
    manager.after_action([_goal()])
    first = play.state.home.view.mentality
    play.state.played_before_s += 60.0
    manager.after_action([_goal()])
    assert play.state.home.view.mentality == first


def test_after_action__a_side_already_all_out_announces_no_change_of_mentality() -> None:
    play, manager = _late_trailing_play()
    play.state.home.view = shift_mentality(play.state.home.view, 9)
    manager.after_action([_goal()])
    assert not [e for e in _of_type(play, TacticalChangeEvent) if e.team == "home"]
    assert play.state.home.view.mentality == 1.0


def test_after_action__with_an_empty_bench_only_the_mentality_changes() -> None:
    play, manager = _late_trailing_play()
    play.state.home.bench.clear()
    manager.after_action([_goal()])
    assert not [e for e in _of_type(play, SubstitutionEvent) if e.team == "home"]
    assert [e for e in _of_type(play, TacticalChangeEvent) if e.team == "home"]


def test_at_halftime__changes_made_at_the_break_use_no_window() -> None:
    config = merge_config(SimConfig(), DECISIVE)
    config = merge_config(config, {"manager": {"chase_from_min": 0.0, "min_fit": 0}})
    play = make_play(seed=3, setup=make_demo_setup(), config=config)
    play.state.played_before_s = 2700.0
    play.state.away.score = 1
    ManagerAI(play, SimRng(5), SimRng(6)).at_halftime()
    assert play.state.home.subs_used >= 1
    assert play.state.home.windows_used == 0


@pytest.mark.parametrize(
    ("rungs", "expected"),
    [(1, "positive"), (-2, "defensive"), (9, "all_out"), (-9, "ultra_defensive")],
)
def test_shift_mentality__moves_along_the_ladder_and_clamps(rungs: int, expected: str) -> None:
    balanced = make_play().state.home.view
    assert mentality_name(balanced) == "balanced"
    assert mentality_name(shift_mentality(balanced, rungs)) == expected


def test_run_match__a_manager_who_never_acts_leaves_the_log_untouched() -> None:
    setup = make_demo_setup()
    quiet = merge_config(SimConfig(), {"manager": {"enabled": True, "stay_weight": 1e12}})
    with_ai = run_match(setup, 21, quiet, default_tables())
    off = merge_config(SimConfig(), {"manager": {"enabled": False}})
    without = run_match(setup, 21, off, default_tables())
    assert with_ai.summary.log_digest == without.summary.log_digest


def test_run_match__managers_make_valid_repeatable_changes() -> None:
    setup = make_demo_setup()
    config = merge_config(SimConfig(), DECISIVE)
    first = run_match(setup, 22, config, default_tables())
    again = run_match(setup, 22, config, default_tables())
    assert_match_valid(first.events, setup)
    assert first.summary.log_digest == again.summary.log_digest
    assert any(isinstance(e, SubstitutionEvent) for e in first.events)
