"""Builder for MatchResult."""

from __future__ import annotations

from footystreams.domain.match import SetupRef
from footystreams.domain.types import ClubId, PlayerId
from footystreams.domain.versions import SIM_VERSION
from footystreams.events.base import MatchClock
from footystreams.events.result import MatchResult
from footystreams.events.structure import FulltimeEvent, KickoffEvent
from footystreams.events.summary import MatchSummary, MatchSummaryEvent
from tests.factories.match import make_setup


def make_match_result() -> MatchResult:
    """Build a minimal valid MatchResult for both tracks' tests."""
    setup = make_setup()
    digest = "a" * 64
    config_hash = "b" * 64
    summary = MatchSummary(
        config_hash=config_hash,
        seed=7,
        log_digest=digest,
        score_home=1,
        score_away=0,
        player_of_the_match=PlayerId("plr_home0000"),
    )
    clock = MatchClock(period=1, minute=0, second=0)
    events = (
        KickoffEvent(
            id=f"{setup.match_id}:00000",
            match_id=setup.match_id,
            seq=0,
            tick=0,
            clock=clock,
        ),
        FulltimeEvent(
            id=f"{setup.match_id}:00001",
            match_id=setup.match_id,
            seq=1,
            tick=5400,
            clock=MatchClock(period=2, minute=90, second=0),
            score_home=1,
            score_away=0,
        ),
        MatchSummaryEvent(
            id=f"{setup.match_id}:00002",
            match_id=setup.match_id,
            seq=2,
            tick=5401,
            clock=MatchClock(period=2, minute=90, second=0),
            summary=summary,
        ),
    )
    return MatchResult(
        events=events,
        summary=summary,
        setup_ref=SetupRef(
            match_id=setup.match_id,
            home_club_id=ClubId("clb_home01"),
            away_club_id=ClubId("clb_away01"),
            fixture_id=setup.fixture_id,
        ),
        seed=7,
        sim_version=SIM_VERSION,
        config_hash=config_hash,
        log_digest=digest,
    )
