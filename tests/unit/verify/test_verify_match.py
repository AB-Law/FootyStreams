from functools import cache

from footystreams.domain.types import Pos
from footystreams.events.clock import match_clock
from footystreams.events.open_play import PassEvent
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, default_tables, run_match
from footystreams.verify import verify_match
from tests.factories.match import make_team_sheet
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.sim import assert_match_valid

SETUP = make_demo_setup()


@cache
def _events() -> tuple[MatchEvent, ...]:
    return run_match(SETUP, 7, SimConfig(), default_tables()).events


def _codes(events: list[MatchEvent]) -> set[str]:
    return {violation.code for violation in verify_match(events)}


def _replace(index: int, **changes: object) -> list[MatchEvent]:
    events = list(_events())
    events[index] = events[index].model_copy(update=changes)
    return events


def test_verify_match__a_simulated_match_has_no_violations() -> None:
    assert_match_valid(_events(), SETUP)


def test_verify_match__empty_log_has_no_violations() -> None:
    assert verify_match([]) == []


def test_m01__a_wrong_seq_is_reported() -> None:
    assert "M01" in _codes(_replace(5, seq=99))


def test_m03__a_duplicate_id_is_reported() -> None:
    events = _replace(5, id=_events()[4].id)
    assert "M03" in _codes(events)


def test_m03__an_id_not_built_from_match_id_and_seq_is_reported() -> None:
    assert "M03" in _codes(_replace(5, id="mch_demo0001:99999"))


def test_m02__a_clock_that_goes_back_is_reported() -> None:
    events = _replace(60, clock=match_clock(1, 0))
    assert "M02" in _codes(events)


def test_m02__a_tick_that_goes_back_is_reported() -> None:
    events = _replace(60, tick=0)
    assert "M02" in _codes(events)


def test_m04__a_context_score_that_disagrees_with_the_goals_is_reported() -> None:
    event = _events()[10]
    bad_ctx = event.ctx.model_copy(update={"score_home": 4})
    assert "M04" in _codes(_replace(10, ctx=bad_ctx))


def test_m04__a_fulltime_score_that_disagrees_is_reported() -> None:
    fulltime_index = len(_events()) - 2
    assert "M04" in _codes(_replace(fulltime_index, score_home=9))


def test_m04__a_summary_score_that_disagrees_is_reported() -> None:
    last = _events()[-1]
    summary = last.summary.model_copy(update={"score_home": 9})  # type: ignore[union-attr]
    assert "M04" in _codes(_replace(len(_events()) - 1, summary=summary))


def test_m10__a_position_outside_the_pitch_is_reported() -> None:
    index = next(i for i, e in enumerate(_events()) if e.pos is not None)
    outside = Pos.model_construct(x=1.5, y=0.5)
    assert "M10" in _codes(_replace(index, pos=outside))


def test_m17__a_log_not_starting_with_a_kickoff_is_reported() -> None:
    assert "M17" in _codes(list(_events())[1:])


def test_m17__an_event_after_fulltime_is_reported() -> None:
    events = list(_events())
    stray = next(e for e in events if isinstance(e, PassEvent))
    events.insert(len(events) - 1, stray)
    assert "M17" in _codes(events)


def test_m17__a_summary_that_is_not_last_is_reported() -> None:
    events = list(_events())
    events.append(events[-2])
    assert "M17" in _codes(events)


def test_m05__a_player_on_both_sheets_is_reported() -> None:
    home = make_team_sheet(side="home")
    away = make_team_sheet(side="away")
    shared = away.model_copy(update={"squad": {**away.squad, **home.squad}})
    setup = make_demo_setup().model_copy(update={"home": home, "away": shared})
    codes = {violation.code for violation in verify_match(_events(), setup)}
    assert "M05" in codes


def test_verify_match__is_repeatable() -> None:
    assert verify_match(_events(), SETUP) == verify_match(_events(), SETUP)
