from collections.abc import Sequence

from footystreams.events.open_play import ShotEvent
from footystreams.events.summary import MatchSummaryEvent, PlayerRating
from footystreams.events.types import MatchEvent
from footystreams.verify import verify_match
from tests.helpers.logs import context_result, demo_setup
from tests.helpers.sim import assert_match_valid


def _events() -> list[MatchEvent]:
    return list(context_result().events)


def _codes(events: Sequence[MatchEvent], *, with_setup: bool = True) -> set[str]:
    return {v.code for v in verify_match(events, demo_setup() if with_setup else None)}


def _with_summary(events: list[MatchEvent], **changes: object) -> list[MatchEvent]:
    last = events[-1]
    assert isinstance(last, MatchSummaryEvent)
    summary = last.summary.model_copy(update=changes)
    return [*events[:-1], last.model_copy(update={"summary": summary})]


def test_verify_match__a_context_enriched_match_with_all_the_m7_checks_is_clean() -> None:
    assert_match_valid(_events(), demo_setup())


def test_m13__an_event_that_no_longer_validates_is_reported() -> None:
    events = _events()
    events[3] = events[3].model_copy(update={"tick": -5})
    assert "M13" in _codes(events)


def test_m14__a_tampered_team_stat_is_reported() -> None:
    events = _events()
    last = events[-1]
    assert isinstance(last, MatchSummaryEvent)
    tampered = last.summary.team_stats_home.model_copy(update={"shots": 99})
    assert "M14" in _codes(_with_summary(events, team_stats_home=tampered))


def test_m14__a_tampered_pass_matrix_is_reported_with_the_field_name() -> None:
    events = _with_summary(_events(), pass_matrix=())
    messages = [v.message for v in verify_match(events, demo_setup()) if v.code == "M14"]
    assert any("pass_matrix" in message for message in messages)


def test_m14__is_skipped_without_a_setup() -> None:
    events = _with_summary(_events(), pass_matrix=())
    assert "M14" not in _codes(events, with_setup=False)


def test_m15__a_rating_out_of_range_is_reported() -> None:
    events = _events()
    last = events[-1]
    assert isinstance(last, MatchSummaryEvent)
    bad = PlayerRating.model_construct(
        player_id=last.summary.ratings[0].player_id, rating=11.5, breakdown={}
    )
    ratings = (bad, *last.summary.ratings[1:])
    assert "M15" in _codes(_with_summary(events, ratings=ratings))


def test_m15__a_row_that_disagrees_with_its_rating_is_reported() -> None:
    events = _events()
    last = events[-1]
    assert isinstance(last, MatchSummaryEvent)
    first = last.summary.player_stats[0]
    rows = (first.model_copy(update={"rating": 3.0 if first.rating != 3.0 else 4.0}),)
    assert "M15" in _codes(_with_summary(events, player_stats=rows + last.summary.player_stats[1:]))


def test_m16__a_wrong_digest_is_reported() -> None:
    assert "M16" in _codes(_with_summary(_events(), log_digest="0" * 64))


def test_m18__out_of_range_context_and_xg_are_reported() -> None:
    events = _events()
    shot = next(i for i, e in enumerate(events) if isinstance(e, ShotEvent))
    events[shot] = events[shot].model_copy(update={"xg": 1.5})
    assert "M18" in _codes(events)
    events = _events()
    context = events[5].ctx.model_copy(update={"momentum": 2.0})
    events[5] = events[5].model_copy(update={"ctx": context})
    assert "M18" in _codes(events)
