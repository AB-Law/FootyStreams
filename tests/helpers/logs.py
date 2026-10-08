"""Find simulated match logs containing a feature (cached), e.g. for a real red card."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from footystreams.domain.match import MatchSetup
from footystreams.events.discipline import CardEvent
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, default_tables, run_match
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
