"""W02: squad sizes, goalkeepers, bench rule and formation coverage for every club."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.player import Player
from footystreams.domain.types import FormationId, Position
from footystreams.domain.world import World
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings
from footystreams.verify.world_targets import WorldChecks, WorldTargets

BACKUP_POSITIONS = (Position.LB, Position.RB, Position.CB, Position.DM, Position.ST)


def _seniors(world: World, club: Club) -> list[Player]:
    return [
        p
        for p in world.players
        if p.contract is not None and p.contract.club_id == club.id and not p.is_youth
    ]


def _competent(players: Sequence[Player], position: Position, floor: int) -> int:
    return sum(p.position_competence.get(position, 0) >= floor for p in players)


def check_squads(world: World, checks: WorldChecks, targets: WorldTargets) -> list[Violation]:
    """W02 for every club."""
    findings = Findings("W02")
    managers = {str(m.id): m for m in world.managers}
    for club in world.clubs:
        seniors = _seniors(world, club)
        _sizes(findings, club, seniors, targets)
        manager = managers.get(str(club.manager_id)) if club.manager_id else None
        formations = {club.default_tactics.formation}
        if manager is not None:
            formations |= {manager.preferred_formation, *manager.fallback_formations}
        for formation_id in sorted(formations):
            _coverage(findings, club, seniors, (checks, targets), formation_id)
        for position in BACKUP_POSITIONS:
            enough = (
                _competent(seniors, position, targets.coverage_competence) >= targets.coverage_depth
            )
            findings.expect(club.id, f"no back-up cover for {position.value}", holds=enough)
    return findings.problems


def _sizes(
    findings: Findings, club: Club, seniors: Sequence[Player], targets: WorldTargets
) -> None:
    low, high = targets.min_senior_squad, targets.max_senior_squad
    findings.expect(
        club.id,
        f"senior squad of {len(seniors)} is outside {low}-{high}",
        holds=low <= len(seniors) <= high,
    )
    keepers = sum(p.primary_position is Position.GK for p in seniors)
    findings.expect(
        club.id, f"only {keepers} goalkeepers", holds=keepers >= targets.min_goalkeepers
    )
    bench_possible = len(seniors) - targets.xi_size >= targets.bench_size and keepers > 1
    findings.expect(
        club.id, "a bench of nine with a goalkeeper cannot be formed", holds=bench_possible
    )


def _coverage(
    findings: Findings,
    club: Club,
    seniors: Sequence[Player],
    rules: tuple[WorldChecks, WorldTargets],
    formation_id: FormationId,
) -> None:
    checks, targets = rules
    formation = checks.formations.formations.get(formation_id)
    if formation is None:
        findings.expect(club.id, f"formation {formation_id} is not in the catalogue", holds=False)
        return
    for position, slots in Counter(formation.positions()).items():
        needed = max(targets.coverage_depth, slots)
        have = _competent(seniors, position, targets.coverage_competence)
        findings.expect(
            club.id,
            f"formation {formation_id}: {have} players cover {position.value}, need {needed}",
            holds=have >= needed,
        )
