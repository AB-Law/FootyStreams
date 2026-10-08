from __future__ import annotations

import pytest
from pydantic import ValidationError

from footystreams.events.broadcast import (
    EngineMarker,
    MarkerKind,
    SegmentEndedEvent,
    SegmentKind,
    SegmentStartedEvent,
    WorldNotice,
    from_line,
    to_line,
)
from footystreams.events.discipline import SubstitutionEvent
from tests.factories.log_builder import LogBuilder

SEGMENT = SegmentStartedEvent(
    id="blk_0001:start",
    block_id="blk_0001",
    kind=SegmentKind.PRE_MATCH,
    subject_ref="fix_t00101",
    duration_s=120.0,
    facts={"home": "Sahus County", "away": "Jymach Rovers", "derby": False, "rank": 3},
)


@pytest.mark.parametrize(
    "event",
    [
        SEGMENT,
        SegmentEndedEvent(id="blk_0001:end", block_id="blk_0001", kind=SegmentKind.PRE_MATCH),
        WorldNotice(
            id="notice:evt_1", world_event_id="evt_1", notice_kind="transfer_completed",
            facts={"fee": 4_000_000},
        ),
        EngineMarker(
            id="marker:resume:1",
            marker=MarkerKind.RESUME,
            resume_match_id="mch_1",
            resume_after_seq=40,
        ),
    ],
)  # fmt: skip
def test_lines__every_engine_event_round_trips_with_its_own_type(event: object) -> None:
    line = to_line(event)  # type: ignore[arg-type]

    assert "\n" not in line
    assert from_line(line) == event


def test_lines__a_match_event_passes_through_unchanged() -> None:
    log = LogBuilder()
    substitution = log.add(SubstitutionEvent, player_off_id="plr_a", player_on_id="plr_b")

    assert from_line(to_line(substitution)) == substitution


def test_lines__an_unknown_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        from_line('{"type": "applause", "id": "x"}')


def test_events__are_frozen_and_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SEGMENT.duration_s = 1.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SegmentEndedEvent(id="x", block_id="b", kind=SegmentKind.FILLER, volume=11)  # type: ignore[call-arg]


def test_segment__a_negative_duration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SegmentStartedEvent(id="x", block_id="b", kind=SegmentKind.FILLER, duration_s=-1.0)
