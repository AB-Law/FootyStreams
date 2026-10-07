"""Squad management in the off-season: promotions, surplus releases, free-agent signings, entries.

Pure. A club keeps between ``min_senior`` and ``max_senior`` senior players and at least
``min_goalkeepers`` keepers. Shortages are filled from the club's own prospects first, then from the
free-agent pool (best available, a short contract); surpluses are released, weakest first.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.player import Player, PlayerStatus, SquadStatus
from footystreams.domain.types import ClubId, PlayerId, Position
from footystreams.domain.valuation import market_value_of, wage_from_value
from footystreams.domain.world import SquadEntry
from footystreams.league.development_config import SquadConfig, YouthConfig
from footystreams.league.youth import contract_end, promoted

FIRST_SENIOR_NUMBER = 12
FIRST_YOUTH_NUMBER = 32
MAX_NUMBER = 99


@dataclass(slots=True)
class SquadMoves:
    """What changed in one club's squad."""

    promoted: list[Player] = field(default_factory=list)
    signed: list[Player] = field(default_factory=list)
    released: list[Player] = field(default_factory=list)


def is_keeper(player: Player) -> bool:
    """True for a goalkeeper."""
    return player.primary_position is Position.GK


def released(player: Player) -> Player:
    """The player after leaving his club for the free-agent pool."""
    return player.model_copy(
        update={
            "contract": None,
            "status": PlayerStatus.FREE_AGENT,
            "squad_status": SquadStatus.FREE_AGENT,
            "squad_number": None,
        }
    )


def signed_free_agent(player: Player, club_id: ClubId, today: dt.date, years: int) -> Player:
    """A free agent signed by a club on a short back-up deal at the going wage."""
    value = market_value_of(player, today)
    contract = Contract(
        club_id=club_id,
        start=today,
        end=contract_end(today, years),
        wage_weekly=wage_from_value(value),
        squad_role=SquadRole.BACKUP,
    )
    return player.model_copy(
        update={
            "contract": contract,
            "status": PlayerStatus.ACTIVE,
            "squad_status": SquadStatus.FIRST_TEAM,
            "is_youth": False,
            "market_value": value,
        }
    )


def _best(candidates: Iterable[Player], *, keeper: bool | None) -> Player | None:
    pool = [c for c in candidates if keeper is None or is_keeper(c) == keeper]
    return max(pool, key=lambda p: (p.ability_current, p.id), default=None)


@dataclass(frozen=True, slots=True)
class SquadContext:
    """Date and rules for a rebalance."""

    today: dt.date
    squad: SquadConfig
    youth: YouthConfig


def rebalance(
    club_id: ClubId, players: Sequence[Player], pool: Sequence[Player], context: SquadContext
) -> SquadMoves:
    """Merit promotions, then fill shortages, then release any surplus."""
    moves = SquadMoves()
    seniors = [p for p in players if not p.is_youth]
    youths = sorted((p for p in players if p.is_youth), key=lambda p: (-p.ability_current, p.id))
    weakest = min((p.ability_current for p in seniors), default=0)
    for youth in youths:
        eligible = youth.age_on(context.today) >= context.youth.promotion_age
        strong = youth.ability_current >= weakest - context.youth.promotion_margin
        if eligible and strong and len(seniors) + len(moves.promoted) < context.squad.max_senior:
            moves.promoted.append(promoted(youth, context.today))
    _fill(club_id, (seniors, youths), pool, (moves, context))
    _release_surplus(seniors, moves, context.squad)
    return moves


def _keepers(seniors: Sequence[Player], moves: SquadMoves) -> int:
    return sum(is_keeper(p) for p in (*seniors, *moves.promoted, *moves.signed))


def _count(seniors: Sequence[Player], moves: SquadMoves) -> int:
    return len(seniors) + len(moves.promoted) + len(moves.signed)


def _fill(
    club_id: ClubId,
    people: tuple[Sequence[Player], Sequence[Player]],
    pool: Sequence[Player],
    state: tuple[SquadMoves, SquadContext],
) -> None:
    seniors, youths = people
    moves, context = state
    left_youths = [y for y in youths if all(y.id != p.id for p in moves.promoted)]
    free = [a for a in pool if a.status is PlayerStatus.FREE_AGENT]
    while _count(seniors, moves) < context.squad.min_senior or (
        _keepers(seniors, moves) < context.squad.min_goalkeepers
    ):
        keeper = True if _keepers(seniors, moves) < context.squad.min_goalkeepers else None
        own = _best(left_youths, keeper=keeper)
        if own is not None:
            left_youths.remove(own)
            moves.promoted.append(promoted(own, context.today))
            continue
        outside = _best(free, keeper=keeper)
        if outside is None:
            return
        free.remove(outside)
        moves.signed.append(
            signed_free_agent(
                outside, club_id, context.today, context.squad.trialist_contract_years
            )
        )


def _release_surplus(seniors: Sequence[Player], moves: SquadMoves, config: SquadConfig) -> None:
    surplus = _count(seniors, moves) - config.max_senior
    keepers = _keepers(seniors, moves)
    candidates = sorted(seniors, key=lambda p: (p.ability_current, p.id))
    for player in candidates:
        if surplus <= 0:
            break
        if is_keeper(player) and keepers <= config.min_goalkeepers:
            continue
        moves.released.append(released(player))
        keepers -= is_keeper(player)
        surplus -= 1


def assign_numbers(players: Sequence[Player]) -> list[Player]:
    """Give shirt numbers to players who have none (seniors from 12, youth from 32)."""
    taken = {p.squad_number for p in players if p.squad_number is not None}
    result: list[Player] = []
    for player in players:
        if player.squad_number is None:
            start = FIRST_YOUTH_NUMBER if player.is_youth else FIRST_SENIOR_NUMBER
            number = next(n for n in range(start, MAX_NUMBER + 1) if n not in taken)
            taken.add(number)
            player = player.model_copy(update={"squad_number": number})  # noqa: PLW2901
        result.append(player)
    return result


def squad_entries(
    club_id: ClubId, players: Sequence[Player], existing: Sequence[SquadEntry]
) -> tuple[list[SquadEntry], list[str]]:
    """Entries the club's squad should have, and the keys of stale existing ones to delete."""
    wanted = [
        SquadEntry(
            club_id=club_id,
            player_id=PlayerId(p.id),
            squad_number=p.squad_number,
            status=p.squad_status,
            squad_role=p.contract.squad_role,
        )
        for p in sorted(players, key=lambda item: item.id)
        if p.contract is not None and p.squad_number is not None
    ]
    keep = {f"{e.club_id}:{e.player_id}" for e in wanted}
    stale = [
        f"{e.club_id}:{e.player_id}" for e in existing if f"{e.club_id}:{e.player_id}" not in keep
    ]
    return wanted, stale
