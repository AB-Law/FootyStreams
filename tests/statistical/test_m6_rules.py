"""M6 sweeps: injuries, changes and tactics appear at sane rates and every log stays valid."""

from collections import Counter

import pytest

from footystreams.events.discipline import InjuryEvent, SubstitutionEvent
from footystreams.sim import SimConfig, default_tables, run_match
from footystreams.verify import verify_match
from tests.factories.sim_teams import make_demo_setup

pytestmark = [pytest.mark.slow, pytest.mark.statistical, pytest.mark.timeout(1800)]

TABLES = default_tables()
FORMATIONS = sorted(TABLES.formations)
MATCHES = 250


def test_sweep__injuries_changes_and_tactics_are_valid_and_plausible() -> None:
    seen: Counter[str] = Counter()
    forced = short = 0
    for index in range(MATCHES):
        setup = make_demo_setup(
            home_strength=54 + (index * 7) % 17,
            away_strength=54 + (index * 11) % 17,
            home_formation=FORMATIONS[index % 8],
            away_formation=FORMATIONS[(index * 3 + 1) % 8],
            match_id=f"mch_sweep{index:04d}",
        )
        events = run_match(setup, 800 + index, SimConfig(), TABLES).events
        assert verify_match(events, setup) == []
        seen.update(event.type for event in events)
        forced += sum(isinstance(e, SubstitutionEvent) and e.reason == "injury" for e in events)
        short += sum(isinstance(e, InjuryEvent) and not e.can_continue for e in events)
    assert 0.25 < seen["injury"] / MATCHES < 0.65
    assert 2.0 < seen["substitution"] / MATCHES < 6.0
    assert 0.8 < seen["tactical_change"] / MATCHES < 6.0
    assert 0.15 < short / max(1, seen["injury"]) < 0.7
    assert forced <= short
