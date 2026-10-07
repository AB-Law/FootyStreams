"""C08: the league has the intended spread of strength (best-vs-worst gap, no near-ties)."""

from __future__ import annotations

from itertools import pairwise

from footystreams.domain.ratings import XI_SIZE
from footystreams.domain.squad_strength import squad_strength
from footystreams.domain.world import World
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings
from footystreams.verify.world_targets import WorldChecks, WorldTargets


def team_ratings(world: World, checks: WorldChecks) -> dict[str, float]:
    """Best-XI team rating of every club for its default tactics (clubs with no XI are skipped)."""
    ratings: dict[str, float] = {}
    for club in world.clubs:
        seniors = [
            p
            for p in world.players
            if p.contract and p.contract.club_id == club.id and not p.is_youth
        ]
        if len(seniors) >= XI_SIZE:
            ratings[str(club.id)] = squad_strength(seniors, club.default_tactics, checks.roles)
    return ratings


def check_league_shape(world: World, checks: WorldChecks, targets: WorldTargets) -> list[Violation]:
    """C08 for the whole league."""
    findings = Findings("C08")
    ranked = sorted(team_ratings(world, checks).items(), key=lambda item: item[1])
    if len(ranked) < 2:  # noqa: PLR2004 - a league needs two clubs to have a spread
        return findings.problems
    gap = ranked[-1][1] - ranked[0][1]
    findings.expect(
        "league",
        f"best-worst gap {gap:.1f} is outside {targets.min_team_gap}-{targets.max_team_gap}",
        holds=targets.min_team_gap <= gap <= targets.max_team_gap,
    )
    for (low_id, low), (high_id, high) in pairwise(ranked):
        findings.expect(
            f"{low_id}/{high_id}",
            f"adjacent clubs are only {high - low:.2f} apart",
            holds=high - low >= targets.min_adjacent_gap,
        )
    return findings.problems
