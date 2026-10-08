"""Pick the strongest eleven for a set of tactical slots and rate it (pure).

One source of truth for "how good is this squad": the seed generator calibrates clubs with it,
the world checks verify the archetype bands with it, and the league's lineup AI starts from it
before applying availability and rotation.
"""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.player import Player
from footystreams.domain.ratings import XI_SIZE, assigned_or_best_role_rating, team_rating
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.tactics import SlotAssignment, TeamTactics
from footystreams.domain.types import Duty, RoleId

Starter = tuple[Player, RoleId, Duty]


def best_lineup(
    players: Sequence[Player], tactics: TeamTactics, catalog: RoleCatalog
) -> tuple[Starter, ...]:
    """Fill each tactical slot, in slot order, with the best remaining player for its role.

    Slot order puts the goalkeeper first, so he is never taken by an outfield role; greedy filling
    is not globally optimal but is deterministic and close enough for strength estimates.
    """
    if len(players) < XI_SIZE:
        msg = f"need at least {XI_SIZE} players to pick a lineup, got {len(players)}"
        raise ValueError(msg)
    remaining = sorted(players, key=lambda player: str(player.id))
    chosen: list[Starter] = []
    for slot in sorted(tactics.slots, key=lambda item: item.slot):
        best = _best_for_slot(remaining, slot, catalog)
        remaining.remove(best)
        chosen.append((best, slot.role, slot.duty))
    return tuple(chosen)


def _best_for_slot(players: Sequence[Player], slot: SlotAssignment, catalog: RoleCatalog) -> Player:
    def fit(player: Player) -> float:
        return assigned_or_best_role_rating(player, catalog, slot.role, slot.duty)

    return max(players, key=fit)


def squad_strength(players: Sequence[Player], tactics: TeamTactics, catalog: RoleCatalog) -> float:
    """Team rating (0-100) of the best lineup the squad can field for ``tactics``."""
    return team_rating(best_lineup(players, tactics, catalog), catalog)
