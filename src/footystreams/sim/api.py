"""The public simulation API: `simulate_match` (stream of events) and `run_match` (full result).

Pure: the same `(setup, seed, config, tables)` always gives the same events, byte for byte
(docs/design/02 section 1). Randomness comes only from `SimRng` streams forked from `seed`.
"""

from __future__ import annotations

from collections.abc import Iterator

from footystreams.domain.match import MatchSetup
from footystreams.domain.referee import Referee
from footystreams.events.result import MatchResult
from footystreams.events.summary import MatchSummaryEvent
from footystreams.events.types import MatchEvent
from footystreams.sim.config import SimConfig, config_hash
from footystreams.sim.engine import MatchEngine
from footystreams.sim.errors import InvalidSetupError
from footystreams.sim.summary import setup_ref
from footystreams.sim.tables import StaticTables


def validate_setup(setup: MatchSetup) -> None:
    """Reject a setup that cannot be simulated, before any event is produced."""
    home_ids = set(setup.home.squad)
    shared = sorted(home_ids & set(setup.away.squad))
    if shared:
        msg = f"players on both sheets of {setup.match_id}: {', '.join(shared)}"
        raise InvalidSetupError(msg)
    if setup.home.club.id == setup.away.club.id:
        msg = f"home and away are the same club {setup.home.club.id} in {setup.match_id}"
        raise InvalidSetupError(msg)


def simulate_match(
    setup: MatchSetup,
    seed: int,
    config: SimConfig,
    tables: StaticTables,
    referee: Referee | None = None,
) -> Iterator[MatchEvent]:
    """Simulate a match and yield its events; the last event is the `match_summary`.

    `referee` is the official named by `setup.referee_id`; `MatchSetup` carries only the id, so the
    caller resolves it. Without one a neutral referee officiates.
    """
    validate_setup(setup)
    return MatchEngine(setup, seed, config, tables, referee).run()


def run_match(
    setup: MatchSetup,
    seed: int,
    config: SimConfig,
    tables: StaticTables,
    referee: Referee | None = None,
) -> MatchResult:
    """Simulate a match to completion and return the events, summary and identity."""
    events = tuple(simulate_match(setup, seed, config, tables, referee))
    last = events[-1]
    if not isinstance(last, MatchSummaryEvent):
        msg = f"match {setup.match_id} ended without a summary"
        raise InvalidSetupError(msg)
    summary = last.summary
    return MatchResult(
        events=events,
        summary=summary,
        setup_ref=setup_ref(setup),
        seed=seed,
        config_hash=config_hash(config),
        log_digest=summary.log_digest,
    )
