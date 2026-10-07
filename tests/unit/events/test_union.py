"""Union discrimination tests for MatchEvent."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from footystreams.domain.types import MatchId, PlayerId
from footystreams.events.base import MatchClock
from footystreams.events.open_play import GoalEvent, PassEvent
from footystreams.events.structure import KickoffEvent
from footystreams.events.types import EVENT_TYPE_NAMES, MATCH_EVENT_ADAPTER


def _clock() -> MatchClock:
    return MatchClock(period=1, minute=0, second=0)


def test_union__kickoff_and_pass_discriminate() -> None:
    kickoff = KickoffEvent(
        id="mch_1:00000",
        match_id=MatchId("mch_test0001"),
        seq=0,
        tick=0,
        clock=_clock(),
    )
    parsed = MATCH_EVENT_ADAPTER.validate_json(kickoff.model_dump_json())
    assert isinstance(parsed, KickoffEvent)
    assert parsed.type == "kickoff"

    pass_event = PassEvent(
        id="mch_1:00001",
        match_id=MatchId("mch_test0001"),
        seq=1,
        tick=10,
        clock=_clock(),
        team="home",
        from_player_id=PlayerId("plr_home0000"),
        to_player_id=PlayerId("plr_home0001"),
    )
    parsed_pass = MATCH_EVENT_ADAPTER.validate_json(pass_event.model_dump_json())
    assert isinstance(parsed_pass, PassEvent)


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


def test_event_type_names__covers_goal() -> None:
    assert "goal" in EVENT_TYPE_NAMES
    assert "kickoff" in EVENT_TYPE_NAMES
    _ = GoalEvent
