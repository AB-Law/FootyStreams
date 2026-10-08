"""Find simulated match logs containing a feature (cached), e.g. for a real red card."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from footystreams.domain.match import MatchSetup
from footystreams.events.discipline import CardEvent
from footystreams.events.open_play import ShotEvent
from footystreams.events.result import MatchResult
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from tests.factories.sim_config import CARD_HEAVY, m5_config
from tests.factories.sim_teams import make_demo_setup

MAX_SEARCH = 30


@cache
def demo_setup() -> MatchSetup:
    """The shared demo setup (immutable, so safe to cache)."""
    return make_demo_setup()


def card_heavy_config() -> SimConfig:
    """M5 behaviour with a foul and card rate high enough for reds in a few matches."""
    return m5_config(CARD_HEAVY)


def _has(log: tuple[MatchEvent, ...], event_type: str) -> bool:
    return any(event.type == event_type for event in log)


def _has_card(log: tuple[MatchEvent, ...], colours: tuple[str, ...]) -> bool:
    return any(isinstance(event, CardEvent) and event.colour in colours for event in log)


@cache
def log_with(feature: str) -> tuple[MatchEvent, ...]:
    """Return the first card-heavy match log that contains the feature."""
    wanted: dict[str, Callable[[tuple[MatchEvent, ...]], bool]] = {
        "red": lambda log: _has_card(log, ("red", "second_yellow")),
        "second_yellow": lambda log: _has_card(log, ("second_yellow",)),
        "yellow": lambda log: _has_card(log, ("yellow",)),
        "penalty": lambda log: _has(log, "penalty"),
        "goal": lambda log: _has(log, "goal"),
        "scoring_shot": lambda log: any(
            isinstance(event, ShotEvent) and event.outcome == "goal" for event in log
        ),
        "save": lambda log: _has(log, "save"),
        "offside": lambda log: _has(log, "offside"),
        "free_kick": lambda log: _has(log, "free_kick"),
    }
    for seed in range(MAX_SEARCH):
        log = run_match(demo_setup(), seed, card_heavy_config(), default_tables()).events
        if wanted[feature](log):
            return log
    msg = f"no card-heavy log with {feature!r} in {MAX_SEARCH} seeds"
    raise LookupError(msg)


INJURY_HEAVY = {
    "injury": {
        "enabled": True,
        "foul_contact": 0.3,
        "tackle_contact": 0.05,
        "non_contact_per_match": 6.0,
    }
}


@cache
def injury_heavy_log() -> tuple[MatchEvent, ...]:
    """A match with plenty of injuries, forced changes and sides playing short."""
    config = merge_config(SimConfig(), INJURY_HEAVY)
    return run_match(demo_setup(), 2, config, default_tables()).events


@cache
def context_result() -> MatchResult:
    """A demo match played with the M7 context and event enrichment switched on."""
    config = merge_config(SimConfig(), {"context": {"enabled": True}})
    return run_match(demo_setup(), 7, config, default_tables())


_ID_FIELDS = ("shot_event_id", "subject_event_id")


def without_frames_renumbered(events: tuple[MatchEvent, ...]) -> list[dict[str, object]]:
    """The non-frame, non-summary events as data with ids and seq renumbered contiguously.

    Frames take sequence numbers, so a log with frames differs from one without in `seq`, `id`
    and the fields that point at ids. After this normalisation the two must be equal.
    """
    kept = [e for e in events if e.type not in ("frame", "match_summary")]
    new_id = {event.id: f"{event.match_id}:{index:05d}" for index, event in enumerate(kept)}
    rows: list[dict[str, object]] = []
    for index, event in enumerate(kept):
        data = event.model_dump()
        data["id"], data["seq"] = new_id[event.id], index
        for name in ("caused_by", *_ID_FIELDS):
            if data.get(name) is not None:
                data[name] = new_id[data[name]]
        rows.append(data)
    return rows
