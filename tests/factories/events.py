"""Minimal valid MatchEvent instances for union discrimination tests."""

from __future__ import annotations

from collections.abc import Callable

from footystreams.domain.types import MatchId, PlayerId
from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION
from footystreams.events.base import EventBase, MatchClock
from footystreams.events.discipline import (
    CardEvent,
    FoulEvent,
    InjuryEvent,
    ReviewEvent,
    SubstitutionEvent,
    TacticalChangeEvent,
)
from footystreams.events.open_play import (
    ClearanceEvent,
    DribbleEvent,
    GoalEvent,
    InterceptionEvent,
    OffsideEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.reserved import (
    CrowdReactionEvent,
    ExtraTimeStartEvent,
    ManagerReactionEvent,
    ShootoutKickEvent,
    VarCheckStartedEvent,
    WeatherChangeEvent,
)
from footystreams.events.restarts import (
    CornerEvent,
    FreeKickEvent,
    GoalKickEvent,
    PenaltyEvent,
    ThrowInEvent,
)
from footystreams.events.structure import (
    AddedTimeEvent,
    FrameEvent,
    FulltimeEvent,
    HalftimeEvent,
    KickoffEvent,
)
from footystreams.events.summary import MatchSummary, MatchSummaryEvent
from footystreams.events.types import EVENT_CLASSES

_MATCH = MatchId("mch_test0001")
_P0 = PlayerId("plr_home0000")
_P1 = PlayerId("plr_home0001")
_P2 = PlayerId("plr_away0000")


def _clock() -> MatchClock:
    return MatchClock(period=1, minute=10, second=0)


def _base(**extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "mch_test0001:00001",
        "match_id": _MATCH,
        "seq": 1,
        "tick": 100,
        "clock": _clock(),
        "team": "home",
    }
    payload.update(extra)
    return payload


def _summary() -> MatchSummary:
    return MatchSummary(
        schema_version=SCHEMA_VERSION,
        sim_version=SIM_VERSION,
        config_hash="cfg",
        seed=1,
        log_digest="digest",
        score_home=1,
        score_away=0,
    )


def _build(cls: type[EventBase], **extra: object) -> EventBase:
    return cls.model_validate(_base(**extra))


_BUILDERS: dict[type[EventBase], Callable[[], EventBase]] = {
    KickoffEvent: lambda: _build(KickoffEvent, id="mch_test0001:00000", seq=0, tick=0),
    FrameEvent: lambda: _build(FrameEvent, ball_pos_x=0.5, ball_pos_y=0.5),
    AddedTimeEvent: lambda: _build(AddedTimeEvent, minutes=3),
    HalftimeEvent: lambda: _build(HalftimeEvent, score_home=0, score_away=0),
    FulltimeEvent: lambda: _build(FulltimeEvent, score_home=1, score_away=0),
    MatchSummaryEvent: lambda: _build(MatchSummaryEvent, summary=_summary()),
    PassEvent: lambda: _build(PassEvent, from_player_id=_P0, to_player_id=_P1),
    DribbleEvent: lambda: _build(DribbleEvent, player_id=_P0),
    TackleEvent: lambda: _build(TackleEvent, player_id=_P0, target_id=_P2),
    InterceptionEvent: lambda: _build(InterceptionEvent, player_id=_P0),
    ClearanceEvent: lambda: _build(ClearanceEvent, player_id=_P0),
    ShotEvent: lambda: _build(ShotEvent, player_id=_P0),
    SaveEvent: lambda: _build(SaveEvent, keeper_id=_P0, shot_event_id="mch_test0001:00010"),
    GoalEvent: lambda: _build(GoalEvent, scorer_id=_P0),
    OffsideEvent: lambda: _build(OffsideEvent, player_id=_P2),
    FoulEvent: lambda: _build(FoulEvent, fouler_id=_P0, fouled_id=_P2),
    CardEvent: lambda: _build(CardEvent, player_id=_P0, colour="yellow"),
    InjuryEvent: lambda: _build(InjuryEvent, player_id=_P0),
    SubstitutionEvent: lambda: _build(SubstitutionEvent, player_off_id=_P0, player_on_id=_P1),
    TacticalChangeEvent: lambda: _build(TacticalChangeEvent),
    ReviewEvent: lambda: _build(ReviewEvent, subject_event_id="mch_test0001:00010"),
    ThrowInEvent: lambda: _build(ThrowInEvent, taker_id=_P0),
    GoalKickEvent: lambda: _build(GoalKickEvent, taker_id=_P0),
    CornerEvent: lambda: _build(CornerEvent, taker_id=_P0),
    FreeKickEvent: lambda: _build(FreeKickEvent, taker_id=_P0),
    PenaltyEvent: lambda: _build(PenaltyEvent, taker_id=_P0),
    ShootoutKickEvent: lambda: _build(ShootoutKickEvent, taker_id=_P0),
    ExtraTimeStartEvent: lambda: _build(ExtraTimeStartEvent, period=3),
    WeatherChangeEvent: lambda: _build(WeatherChangeEvent, condition="rain"),
    CrowdReactionEvent: lambda: _build(CrowdReactionEvent),
    ManagerReactionEvent: lambda: _build(ManagerReactionEvent),
    VarCheckStartedEvent: lambda: _build(
        VarCheckStartedEvent, subject_event_id="mch_test0001:00010"
    ),
}


def make_event(cls: type[EventBase]) -> EventBase:
    """Build a minimal valid instance of ``cls``."""
    try:
        return _BUILDERS[cls]()
    except KeyError as exc:
        msg = f"no factory for {cls.__name__}"
        raise KeyError(msg) from exc


def assert_builders_cover_union() -> None:
    """Fail fast if EVENT_CLASSES and builders drift apart."""
    missing = set(EVENT_CLASSES) - set(_BUILDERS)
    extra = set(_BUILDERS) - set(EVENT_CLASSES)
    if missing or extra:
        missing_names = sorted(cls.__name__ for cls in missing)
        extra_names = sorted(cls.__name__ for cls in extra)
        msg = f"event factory drift missing={missing_names} extra={extra_names}"
        raise AssertionError(msg)
