from footystreams.events.context import ContextTag
from footystreams.events.derive.context import ContextTracker
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from tests.factories.sim_teams import make_demo_setup
from tests.helpers.logs import context_result
from tests.helpers.sim import assert_match_valid


def test_run_match__with_context_on_the_log_is_valid_and_carries_momentum_and_tags() -> None:
    events = context_result().events
    assert_match_valid(events, make_demo_setup())
    assert any(event.ctx.momentum != 0.0 for event in events)
    assert any(event.ctx.intensity != 0.5 for event in events)
    assert any(ContextTag.LATE_GAME in event.ctx.tags for event in events)


def test_run_match__replaying_the_tracker_over_the_log_reproduces_every_context() -> None:
    events = context_result().events[:-1]  # the summary event is outside the tracker's remit
    tracker = ContextTracker(is_derby=make_demo_setup().is_derby)
    replayed = [tracker.annotate(event) for event in events]
    assert [event.ctx for event in replayed] == [event.ctx for event in events]


def test_run_match__with_context_off_events_carry_the_default_context() -> None:
    off = merge_config(SimConfig(), {"context": {"enabled": False}})
    events = run_match(make_demo_setup(), 7, off, default_tables()).events
    assert all(event.ctx.momentum == 0.0 and not event.ctx.tags for event in events[:30])


def _without_context(event: MatchEvent) -> dict[str, object]:
    """The event as data without the fields context and enrichment own."""
    data = event.model_dump()
    for name in ("momentum", "intensity", "significance", "tags"):
        data["ctx"].pop(name)
    for name in (
        "end_pos",
        "skill_move",
        "progressive",
        "xt_gain",
        "big_chance",
        "target",
        "curve",
        "speed_mps",
        "loft",
    ):
        data.pop(name, None)
    return data


def test_run_match__turning_context_on_changes_only_context_and_enrichment() -> None:
    off = merge_config(SimConfig(), {"context": {"enabled": False}})
    plain = run_match(make_demo_setup(), 7, off, default_tables()).events[:-1]
    assert [_without_context(event) for event in plain] == [
        _without_context(event) for event in context_result().events[:-1]
    ]


def test_sim_config__context_is_on_by_default() -> None:
    assert SimConfig().context.enabled
