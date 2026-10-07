"""W03: balance equals the opening ledger; wage bills sit near budget."""

from __future__ import annotations

from collections import defaultdict

from footystreams.domain.world import World
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings
from footystreams.verify.world_targets import WorldTargets


def check_money(world: World, targets: WorldTargets) -> list[Violation]:
    """W03 balance == sum(opening ledger) per club, and the wage-bill bands."""
    ledger: dict[str, int] = defaultdict(int)
    for entry in world.ledger_opening:
        ledger[str(entry.club_id)] += entry.amount
    wage_bill: dict[str, int] = defaultdict(int)
    for player in world.players:
        if player.contract is not None:
            wage_bill[str(player.contract.club_id)] += player.contract.wage_weekly
    findings = Findings("W03")
    overspenders = 0
    for club in world.clubs:
        finances = club.finances
        findings.expect(
            club.id,
            f"balance {finances.balance} differs from the ledger sum {ledger[str(club.id)]}",
            holds=finances.balance == ledger[str(club.id)],
        )
        ratio = (
            wage_bill[str(club.id)] / finances.wage_budget_weekly
            if finances.wage_budget_weekly
            else 0.0
        )
        findings.expect(
            club.id,
            f"wage bill is {ratio:.0%} of the budget",
            holds=targets.min_wage_ratio <= ratio <= targets.max_wage_ratio,
        )
        overspenders += ratio > targets.overspend_ratio
    findings.expect(
        "league",
        f"{overspenders} clubs overspend deliberately; at most {targets.max_overspenders} may",
        holds=overspenders <= targets.max_overspenders,
    )
    return findings.problems
