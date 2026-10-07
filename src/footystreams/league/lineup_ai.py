"""Pick the eleven and the bench: availability, fit for each slot, rotation, set-piece takers.

Pure. The manager's formation and role assignments come from the club's default tactics; this
module only decides *who* fills each slot (docs/design/07 section 2, stage 8).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.match import CornerTakers, LineupSlot
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.ratings import assigned_or_best_role_rating
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import Formation
from footystreams.domain.tactics import SlotAssignment, TeamTactics
from footystreams.domain.types import PlayerId, Position, PreferredFoot
from footystreams.league.config import RecoveryConfig

BENCH_SIZE = 7
PENALTY_TAKERS = 3
FREE_KICK_TAKERS = 2
XI_SIZE = 11


class SquadTooSmallError(ValueError):
    """Fewer than eleven players exist at all, even counting the injured."""


@dataclass(frozen=True, slots=True)
class Selection:
    """The eleven (in slot order), the bench and the set-piece duties."""

    lineup: tuple[LineupSlot, ...]
    bench: tuple[PlayerId, ...]
    captain: PlayerId
    penalty_takers: tuple[PlayerId, ...]
    free_kick_takers: tuple[PlayerId, ...]
    corner_takers: CornerTakers


@dataclass(frozen=True, slots=True)
class SelectionTables:
    """Static inputs of the selection."""

    roles: RoleCatalog
    recovery: RecoveryConfig


def player_id(player: Player) -> PlayerId:
    """The player's id as a ``PlayerId`` (people carry the generic ``Id`` type)."""
    return PlayerId(player.id)


def is_available(player: Player, today: dt.date) -> bool:
    """Registered, fit and not banned."""
    if player.status is not PlayerStatus.ACTIVE or player.suspension is not None:
        return False
    injury = player.current_injury
    return injury is None or injury.expected_return_on <= today


def _value(player: Player, assignment: SlotAssignment, tables: SelectionTables) -> float:
    """How good the player is in the slot today; a tired player is marked down so he is rotated."""
    rating = assigned_or_best_role_rating(player, tables.roles, assignment.role, assignment.duty)
    tired = player.fatigue > tables.recovery.rotation_fatigue_threshold
    return rating - (tables.recovery.rotation_ability_margin if tired else 0)


def assign_slots(
    pool: Sequence[Player], tactics: TeamTactics, tables: SelectionTables
) -> dict[int, Player]:
    """Best (slot, player) pairs first, so a scarce position is filled before a plentiful one."""
    pairs = sorted(
        (-_value(player, assignment, tables), assignment.slot, player.id)
        for assignment in tactics.slots
        for player in pool
    )
    by_id = {player.id: player for player in pool}
    chosen: dict[int, Player] = {}
    used: set[str] = set()
    for _, slot, player_id in pairs:
        if slot not in chosen and player_id not in used:
            chosen[slot] = by_id[player_id]
            used.add(player_id)
    return chosen


def _bench(rest: Sequence[Player]) -> tuple[PlayerId, ...]:
    """The best spare keeper first, then the best of the rest by current ability."""
    ranked = sorted(rest, key=lambda player: (-player.ability_current, player.id))
    keepers = [p for p in ranked if p.primary_position is Position.GK][:1]
    others = [p for p in ranked if p not in keepers][: BENCH_SIZE - len(keepers)]
    return tuple(player_id(player) for player in (*keepers, *others))


def _best(starters: Sequence[Player], score: str, count: int) -> tuple[PlayerId, ...]:
    ranked = sorted(starters, key=lambda p: (-_attribute(p, score), p.id))
    return tuple(player_id(player) for player in ranked[:count])


def _attribute(player: Player, name: str) -> int:
    for group in (player.technical, player.mental):
        if hasattr(group, name):
            return int(getattr(group, name))
    return 0


def _corner_takers(starters: Sequence[Player]) -> CornerTakers:
    ranked = sorted(starters, key=lambda p: (-p.technical.set_piece_delivery, p.id))

    def side(foot: PreferredFoot, avoid: str | None) -> PlayerId:
        pool = [p for p in ranked if p.id != avoid] or ranked
        return player_id(next((p for p in pool if p.preferred_foot is foot), pool[0]))

    left = side(PreferredFoot.LEFT, None)
    return CornerTakers(left=left, right=side(PreferredFoot.RIGHT, left))


def select_squad(
    squad: Sequence[Player],
    formation: Formation,
    tactics: TeamTactics,
    context: tuple[dt.date, SelectionTables],
) -> Selection:
    """Choose the XI, bench and takers from ``squad`` for a match on the given date.

    Unavailable players are used only when fewer than eleven are fit (never fails a match).
    """
    today, tables = context
    fit = [p for p in squad if is_available(p, today)]
    reserve = [p for p in squad if p not in fit]
    if len(fit) + len(reserve) < XI_SIZE:
        msg = f"only {len(squad)} players available to pick from"
        raise SquadTooSmallError(msg)
    chosen = assign_slots(fit if len(fit) >= XI_SIZE else [*fit, *reserve], tactics, tables)
    starters = [chosen[slot.slot] for slot in formation.slots]
    assignments = {a.slot: a for a in tactics.slots}
    lineup = tuple(
        LineupSlot(
            slot=slot.slot,
            player_id=player_id(chosen[slot.slot]),
            role=assignments[slot.slot].role,
            duty=assignments[slot.slot].duty,
        )
        for slot in formation.slots
    )
    used = {p.id for p in starters}
    spare = [p for p in fit if p.id not in used]
    return Selection(
        lineup=lineup,
        bench=_bench(spare),
        captain=_best(starters, "leadership", 1)[0],
        penalty_takers=_best(starters, "penalty_taking", PENALTY_TAKERS),
        free_kick_takers=_best(starters, "set_piece_delivery", FREE_KICK_TAKERS),
        corner_takers=_corner_takers(starters),
    )
