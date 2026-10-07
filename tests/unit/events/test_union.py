"""Union discrimination tests for every MatchEvent type."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from footystreams.events.base import EventBase
from footystreams.events.types import EVENT_CLASSES, EVENT_TYPE_NAMES, MATCH_EVENT_ADAPTER
from tests.factories.events import assert_builders_cover_union, make_event


def test_event_builders__cover_union_members() -> None:
    assert_builders_cover_union()
    assert len(EVENT_CLASSES) == len(EVENT_TYPE_NAMES) == 32


@pytest.mark.parametrize("cls", EVENT_CLASSES, ids=lambda c: c.__name__)
def test_union__each_type_parses_to_own_class(cls: type[EventBase]) -> None:
    event = make_event(cls)
    parsed = MATCH_EVENT_ADAPTER.validate_json(event.model_dump_json())
    assert type(parsed) is cls
    assert parsed.type == cls.model_fields["type"].default


def test_union__unknown_type__rejected() -> None:
    with pytest.raises(ValidationError):
        MATCH_EVENT_ADAPTER.validate_python(
            {
                "id": "mch_1:00000",
                "match_id": "mch_test0001",
                "seq": 0,
                "tick": 0,
                "type": "not_a_real_event",
                "clock": {"period": 1, "minute": 0, "second": 0},
            }
        )
