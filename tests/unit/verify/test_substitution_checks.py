from collections.abc import Sequence

from footystreams.events.base import MatchClock
from footystreams.events.discipline import SubstitutionEvent
from footystreams.events.types import MatchEvent
from footystreams.verify import verify_match
from tests.helpers.logs import demo_setup, injury_heavy_log


def _codes(events: Sequence[MatchEvent]) -> set[str]:
    return {violation.code for violation in verify_match(events, demo_setup())}


def _template() -> tuple[int, SubstitutionEvent]:
    for index, event in enumerate(injury_heavy_log()):
        if isinstance(event, SubstitutionEvent) and event.team == "home":
            return index, event
    raise AssertionError("the log has no home substitution")


def _changes_at(minutes: Sequence[int], reason: str, period: int = 2) -> list[MatchEvent]:
    """Append home changes (copies of a real one) at the given minutes to the log's tail."""
    _, template = _template()
    log = list(injury_heavy_log())
    tail = log[-2:]
    extra = [
        template.model_copy(
            update={"reason": reason, "clock": MatchClock(period=period, minute=minute, second=0)}
        )
        for minute in minutes
    ]
    return [*log[:-2], *extra, *tail]


def _problems(events: Sequence[MatchEvent], code: str) -> list[str]:
    return [v.message for v in verify_match(events, demo_setup()) if v.code == code]


def test_m06__a_player_taken_off_who_is_not_on_the_pitch_is_reported() -> None:
    index, change = _template()
    log = list(injury_heavy_log())
    log[index] = change.model_copy(update={"player_off_id": change.player_on_id})
    assert "player taken off is not on the pitch" in _problems(log, "M06")


def test_m06__a_player_brought_on_who_is_not_an_unused_sub_is_reported() -> None:
    index, change = _template()
    log = list(injury_heavy_log())
    log[index] = change.model_copy(update={"player_on_id": change.player_off_id})
    assert "player brought on is not an unused sub" in _problems(log, "M06")


def test_m06__a_real_log_with_changes_and_sides_short_is_clean() -> None:
    assert not _problems(list(injury_heavy_log()), "M06")


def test_m08__more_changes_than_the_rules_allow_is_reported() -> None:
    log = _changes_at([50, 51, 52, 53, 54, 55, 56], "injury")
    assert any("changes" in problem for problem in _problems(log, "M08"))


def test_m08__changes_in_too_many_stoppages_are_reported() -> None:
    log = _changes_at([50, 60, 70, 80], "tactical")
    assert any("windows" in problem for problem in _problems(log, "M08"))


def test_m08__injury_and_half_time_changes_need_no_window() -> None:
    injured = _changes_at([50, 60, 70, 80], "injury")
    at_break = _changes_at([45, 45, 45, 45], "tactical", period=1)
    assert not [p for p in _problems(injured, "M08") if "windows" in p]
    assert not [p for p in _problems(at_break, "M08") if "windows" in p]


def test_m08__changes_close_together_share_a_window() -> None:
    log = _changes_at([60, 60, 60, 60], "tactical")
    assert not [p for p in _problems(log, "M08") if "windows" in p]


def test_m06__a_twelfth_man_is_reported() -> None:
    _, change = _template()
    log = list(injury_heavy_log())
    off, on = demo_setup().home.bench[:2]
    extra = change.model_copy(update={"player_off_id": off, "player_on_id": on, "seq": 1})
    log.insert(1, extra)
    assert any("players on the pitch" in problem for problem in _problems(log, "M06"))
