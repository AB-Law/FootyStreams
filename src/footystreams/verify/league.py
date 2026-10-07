"""L01-L03: a running league is internally consistent (money, results, schedule)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.finance import LedgerEntry
from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.match import Match, MatchStatus
from footystreams.events.summary import MatchSummary
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings


def check_ledger(clubs: Sequence[Club], entries: Sequence[LedgerEntry]) -> list[Violation]:
    """L01: a club's balance equals its ledger sum; ledger entry ids are unique."""
    findings = Findings("L01")
    totals: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    for entry in entries:
        totals[str(entry.club_id)] += entry.amount
        findings.expect(entry.id, "ledger entry id appears twice", holds=entry.id not in seen)
        seen.add(entry.id)
    for club in clubs:
        balance, ledger = club.finances.balance, totals[str(club.id)]
        findings.expect(
            club.id,
            f"balance {balance} differs from the ledger sum {ledger}",
            holds=balance == ledger,
        )
    return findings.problems


def check_results(
    fixtures: Sequence[Fixture],
    matches: Sequence[Match],
    summaries: dict[str, MatchSummary],
) -> list[Violation]:
    """L02: every played fixture has one completed match whose score is the summary's."""
    findings = Findings("L02")
    by_fixture = {str(m.fixture_id): m for m in matches}
    for fixture in fixtures:
        match = by_fixture.get(fixture.id)
        played = fixture.status is FixtureStatus.PLAYED
        findings.expect(
            fixture.id, "played fixture has no match", holds=(match is not None) == played
        )
        if match is None:
            continue
        findings.expect(
            match.id,
            "match is not completed",
            holds=match.status is MatchStatus.COMPLETED,
        )
        findings.expect(
            match.id,
            "match clubs differ from the fixture's",
            holds=(match.home_club_id, match.away_club_id)
            == (fixture.home_club_id, fixture.away_club_id),
        )
        summary = summaries.get(match.id)
        findings.expect(match.id, "match has no stored summary", holds=summary is not None)
        if summary is not None:
            findings.expect(
                match.id,
                "match score differs from its summary",
                holds=(match.home_goals, match.away_goals)
                == (summary.score_home, summary.score_away),
            )
    return findings.problems


def check_season_complete(fixtures: Sequence[Fixture]) -> list[Violation]:
    """L03: when a season is over, every fixture was played."""
    findings = Findings("L03")
    for fixture in fixtures:
        findings.expect(
            fixture.id,
            f"fixture is {fixture.status.value}, not played",
            holds=fixture.status is FixtureStatus.PLAYED,
        )
    return findings.problems
