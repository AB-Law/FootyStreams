"""Fast checks on real M5 logs: sequencing, dismissals and the shapes the renderer will print."""

from footystreams.events.discipline import CardEvent, FoulEvent
from footystreams.events.restarts import CornerEvent, FreeKickEvent, PenaltyEvent
from footystreams.events.structure import AddedTimeEvent
from tests.helpers.logs import demo_setup, log_with
from tests.helpers.sim import assert_match_valid


def test_card_heavy_log__is_valid_and_contains_the_dead_ball_events() -> None:
    log = log_with("red")
    assert_match_valid(log, demo_setup())
    kinds = {type(event) for event in log}
    assert {FoulEvent, CardEvent, FreeKickEvent, AddedTimeEvent} <= kinds


def test_card_heavy_log__penalties_and_corners_appear_across_the_helper_logs() -> None:
    assert any(isinstance(e, PenaltyEvent) for e in log_with("penalty"))
    corners = (
        e for feature in ("goal", "save") for e in log_with(feature) if isinstance(e, CornerEvent)
    )
    assert next(corners, None) is not None


def test_card_heavy_log__men_never_exceed_eleven_or_drop_below_seven() -> None:
    for event in log_with("red"):
        assert 7 <= event.ctx.men_home <= 11
        assert 7 <= event.ctx.men_away <= 11
