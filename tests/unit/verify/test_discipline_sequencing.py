from collections.abc import Sequence

import pytest

from footystreams.events.discipline import CardEvent, FoulEvent
from footystreams.events.open_play import (
    GoalEvent,
    OffsideEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.restarts import FreeKickEvent, PenaltyEvent
from footystreams.events.types import MatchEvent
from footystreams.verify import verify_match
from tests.helpers.logs import demo_setup, log_with
from tests.helpers.sim import assert_match_valid


def _codes(events: Sequence[MatchEvent]) -> set[str]:
    return {violation.code for violation in verify_match(events)}


def _first(events: Sequence[MatchEvent], kind: type) -> int:
    return next(i for i, event in enumerate(events) if isinstance(event, kind))


@pytest.mark.parametrize("feature", ["red", "second_yellow", "penalty", "goal", "save", "offside"])
def test_verify_match__real_logs_with_every_m5_feature_are_clean(feature: str) -> None:
    assert_match_valid(log_with(feature), demo_setup())


def test_m07__a_sent_off_player_named_in_a_later_event_is_reported() -> None:
    log = list(log_with("red"))
    index = next(i for i, e in enumerate(log) if isinstance(e, CardEvent) and e.colour != "yellow")
    card = log[index]
    assert isinstance(card, CardEvent)
    template = next(e for e in log[index + 1 :] if isinstance(e, PassEvent))
    ghost = template.model_copy(update={"from_player_id": card.player_id})
    log.insert(index + 1, ghost)
    assert "M07" in _codes(log)


def test_m11__a_second_plain_yellow_for_the_same_player_is_reported() -> None:
    log = list(log_with("yellow"))
    index = next(i for i, e in enumerate(log) if isinstance(e, CardEvent) and e.colour == "yellow")
    log.insert(index + 1, log[index])
    assert "M11" in _codes(log)


def test_m11__a_second_yellow_without_a_first_is_reported() -> None:
    log = list(log_with("yellow"))
    index = next(i for i, e in enumerate(log) if isinstance(e, CardEvent) and e.colour == "yellow")
    log[index] = log[index].model_copy(update={"colour": "second_yellow"})
    assert "M11" in _codes(log)


def test_m11__a_card_after_dismissal_is_reported() -> None:
    log = list(log_with("red"))
    index = next(i for i, e in enumerate(log) if isinstance(e, CardEvent) and e.colour != "yellow")
    log.insert(index + 1, log[index])
    assert "M11" in _codes(log)


def test_m11__a_wrong_men_count_in_the_context_is_reported() -> None:
    log = list(log_with("red"))
    event = log[5]
    log[5] = event.model_copy(update={"ctx": event.ctx.model_copy(update={"men_home": 9})})
    assert "M11" in _codes(log)


def test_m12__a_cause_that_does_not_exist_is_reported() -> None:
    log = list(log_with("goal"))
    log[10] = log[10].model_copy(update={"caused_by": "mch_demo0001:99999"})
    assert "M12" in _codes(log)


def test_m12__a_cause_that_comes_later_is_reported() -> None:
    log = list(log_with("goal"))
    log[10] = log[10].model_copy(update={"caused_by": log[20].id})
    assert "M12" in _codes(log)


def test_m12__a_scoring_shot_without_its_goal_is_reported() -> None:
    log = list(log_with("goal"))
    shot_index = next(
        i for i, e in enumerate(log) if isinstance(e, ShotEvent) and e.outcome == "goal"
    )
    del log[shot_index + 1]
    assert "M12" in _codes(log)


def test_m12__a_saved_shot_without_its_save_is_reported() -> None:
    log = list(log_with("save"))
    shot_index = next(
        i for i, e in enumerate(log) if isinstance(e, ShotEvent) and e.outcome == "saved"
    )
    del log[shot_index + 1]
    assert "M12" in _codes(log)


def test_m12__a_goal_not_caused_by_a_scoring_shot_is_reported() -> None:
    log = list(log_with("goal"))
    index = _first(log, GoalEvent)
    log[index] = log[index].model_copy(update={"shot_event_id": log[0].id})
    assert "M12" in _codes(log)


def test_m12__a_save_not_caused_by_a_saved_shot_is_reported() -> None:
    log = list(log_with("save"))
    index = _first(log, SaveEvent)
    log[index] = log[index].model_copy(update={"shot_event_id": log[0].id})
    assert "M12" in _codes(log)


def test_m12__a_card_not_caused_by_the_foul_of_the_booked_player_is_reported() -> None:
    log = list(log_with("yellow"))
    index = _first(log, CardEvent)
    log[index] = log[index].model_copy(update={"caused_by": log[0].id})
    assert "M12" in _codes(log)


def test_m12__a_free_kick_with_no_foul_or_offside_cause_is_reported() -> None:
    log = list(log_with("free_kick"))
    index = _first(log, FreeKickEvent)
    log[index] = log[index].model_copy(update={"caused_by": log[0].id})
    assert "M12" in _codes(log)


def test_m12__a_penalty_not_caused_by_a_foul_is_reported() -> None:
    log = list(log_with("penalty"))
    index = _first(log, PenaltyEvent)
    log[index] = log[index].model_copy(update={"caused_by": log[0].id})
    assert "M12" in _codes(log)


def test_m12__a_foul_not_caused_by_its_tackle_is_reported() -> None:
    log = list(log_with("yellow"))
    index = _first(log, FoulEvent)
    log[index] = log[index].model_copy(update={"caused_by": log[0].id})
    assert "M12" in _codes(log)


def test_m12__an_offside_without_a_cause_is_reported() -> None:
    log = list(log_with("offside"))
    index = _first(log, OffsideEvent)
    log[index] = log[index].model_copy(update={"caused_by": None})
    assert "M12" in _codes(log)


def test_m12__a_foul_after_a_tackle_is_the_normal_chain() -> None:
    log = log_with("yellow")
    index = _first(log, FoulEvent)
    assert isinstance(log[index - 1], TackleEvent)
    assert log[index].caused_by == log[index - 1].id
