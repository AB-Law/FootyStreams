"""Assertions for simulated matches: they call `verify/`, never re-implement a rule."""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.match import MatchSetup
from footystreams.events.types import MatchEvent
from footystreams.verify import verify_match
from tests.helpers.assertions import assert_no_violations


def assert_match_valid(events: Sequence[MatchEvent], setup: MatchSetup | None = None) -> None:
    """Fail with every violated match invariant, if any."""
    assert_no_violations(verify_match(events, setup))
