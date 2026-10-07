from collections.abc import Sequence

from footystreams.events.discipline import InjuryEvent, SubstitutionEvent
from footystreams.events.open_play import PassEvent
from footystreams.events.types import MatchEvent
from footystreams.verify import verify_match
from footystreams.verify.discipline import injured_off_unreplaced
from tests.helpers.logs import demo_setup, injury_heavy_log
from tests.helpers.sim import assert_match_valid


def _codes(events: Sequence[MatchEvent]) -> set[str]:
    return {violation.code for violation in verify_match(events)}


def _first_index(kind: type) -> int:
    return next(i for i, event in enumerate(injury_heavy_log()) if isinstance(event, kind))


def test_verify_match__an_injury_heavy_log_is_clean() -> None:
    assert_match_valid(injury_heavy_log(), demo_setup())


def test_injured_off_unreplaced__a_change_that_follows_makes_it_replaced() -> None:
    log = injury_heavy_log()
    replaced = next(
        i
        for i, event in enumerate(log)
        if isinstance(event, InjuryEvent) and isinstance(log[i + 1], SubstitutionEvent)
    )
    assert not injured_off_unreplaced(log, replaced)


def test_m07__a_substituted_player_named_again_is_reported() -> None:
    log = list(injury_heavy_log())
    index = _first_index(SubstitutionEvent)
    change = log[index]
    assert isinstance(change, SubstitutionEvent)
    template = next(e for e in log[index + 1 :] if isinstance(e, PassEvent))
    log.insert(index + 1, template.model_copy(update={"from_player_id": change.player_off_id}))
    assert "M07" in _codes(log)


def test_m11__an_unreplaced_injury_that_keeps_the_men_count_is_reported() -> None:
    log = list(injury_heavy_log())
    short = next(i for i in range(len(log)) if injured_off_unreplaced(log, i))
    event = log[short]
    wrong = event.ctx.model_copy(update={"men_home": 11, "men_away": 11})
    log[short] = event.model_copy(update={"ctx": wrong})
    assert "M11" in _codes(log)
