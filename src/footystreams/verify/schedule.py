"""W12: a valid double round-robin schedule."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Collection, Sequence

from footystreams.domain.fixture import Fixture
from footystreams.domain.types import ClubId
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings

MAX_STREAK = 2


def _streak_findings(
    findings: Findings, fixtures: Sequence[Fixture], clubs: Collection[ClubId]
) -> None:
    by_club: dict[ClubId, list[tuple[int, bool]]] = defaultdict(list)
    for fixture in fixtures:
        by_club[fixture.home_club_id].append((fixture.matchday, True))
        by_club[fixture.away_club_id].append((fixture.matchday, False))
    for club in clubs:
        longest = run = 0
        previous: bool | None = None
        for _, at_home in sorted(by_club[club]):
            run = run + 1 if at_home == previous else 1
            previous = at_home
            longest = max(longest, run)
        findings.expect(
            club, f"{longest} home or away matches in a row", holds=longest <= MAX_STREAK
        )


def check_schedule(
    fixtures: Sequence[Fixture],
    clubs: Sequence[ClubId],
    derbies: Collection[frozenset[ClubId]] = (),
) -> list[Violation]:
    """Each ordered pair once, no club twice in a matchday, short streaks, no early derby."""
    findings = Findings("W12")
    pairs = Counter((f.home_club_id, f.away_club_id) for f in fixtures)
    for home in clubs:
        for away in clubs:
            if home != away:
                findings.expect(
                    f"{home}/{away}",
                    f"home fixture appears {pairs[(home, away)]} times, not once",
                    holds=pairs[(home, away)] == 1,
                )
    for fixture in fixtures:
        findings.expect(
            fixture.id, "a club plays itself", holds=fixture.home_club_id != fixture.away_club_id
        )
    appearances = Counter(
        (f.matchday, club) for f in fixtures for club in (f.home_club_id, f.away_club_id)
    )
    for (matchday, club), count in appearances.items():
        findings.expect(club, f"plays {count} times on matchday {matchday}", holds=count == 1)
    for fixture in fixtures:
        is_derby = frozenset({fixture.home_club_id, fixture.away_club_id}) in derbies
        findings.expect(
            fixture.id, "derby on matchday 1", holds=not (is_derby and fixture.matchday == 1)
        )
    _streak_findings(findings, fixtures, clubs)
    return findings.problems
