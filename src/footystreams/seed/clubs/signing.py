"""Sign a squad: shirt numbers, squad roles, contracts, valuations and the wage scale."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.player import Player, SquadStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Money, PlayerId, Position
from footystreams.domain.world import SquadEntry
from footystreams.seed.players.contract import contract_for, market_value_of

KEY_PLAYERS = 7
ROTATION_PLAYERS = 7
YOUTH_NUMBER_START = 32
MAX_SHIRT_NUMBER = 99
FIRST_FREE_NUMBER = 12


@dataclass(frozen=True, slots=True)
class WageTarget:
    """Where the squad's weekly wage bill should land."""

    budget_weekly: Money
    ratio: float


def assign_numbers(
    players: Sequence[Player], preferences: Mapping[Position, tuple[int, ...]]
) -> dict[PlayerId, int]:
    """Preferred numbers by position first, then the lowest free number; youth start at 32."""
    taken: set[int] = set()
    numbers: dict[PlayerId, int] = {}
    for player in (p for p in players if not p.is_youth):
        for candidate in preferences.get(player.primary_position, ()):
            if candidate not in taken:
                numbers[PlayerId(str(player.id))] = candidate
                taken.add(candidate)
                break
    free = (n for n in range(FIRST_FREE_NUMBER, MAX_SHIRT_NUMBER + 1) if n not in taken)
    for player in (p for p in players if not p.is_youth):
        key = PlayerId(str(player.id))
        if key not in numbers:
            numbers[key] = next(free)
            taken.add(numbers[key])
    next_youth = max(YOUTH_NUMBER_START, max(taken, default=0) + 1)
    for player in (p for p in players if p.is_youth):
        while next_youth in taken:
            next_youth += 1
        numbers[PlayerId(str(player.id))] = next_youth
        taken.add(next_youth)
    return numbers


def squad_roles(players: Sequence[Player]) -> dict[PlayerId, SquadRole]:
    """Key players are the seven best seniors, then seven rotation players, then back-ups."""
    seniors = sorted(
        (p for p in players if not p.is_youth),
        key=lambda p: (-p.ability_current, str(p.id)),
    )
    roles: dict[PlayerId, SquadRole] = {}
    for rank, player in enumerate(seniors):
        if rank < KEY_PLAYERS:
            role = SquadRole.KEY
        elif rank < KEY_PLAYERS + ROTATION_PLAYERS:
            role = SquadRole.ROTATION
        else:
            role = SquadRole.BACKUP
        roles[PlayerId(str(player.id))] = role
    for player in (p for p in players if p.is_youth):
        roles[PlayerId(str(player.id))] = SquadRole.PROSPECT
    return roles


def _scaled(contract: Contract, factor: float) -> Contract:
    return contract.model_copy(
        update={
            "wage_weekly": round(contract.wage_weekly * factor),
            "appearance_bonus": round(contract.appearance_bonus * factor),
            "goal_bonus": round(contract.goal_bonus * factor),
            "clean_sheet_bonus": round(contract.clean_sheet_bonus * factor),
        }
    )


def sign_squad(
    players: Sequence[Player],
    club_id: ClubId,
    numbers: Mapping[PlayerId, int],
    rng: WorldRng,
    today: dt.date,
) -> list[Player]:
    """Give every player a number, a squad role, a contract and a value that reflects it."""
    roles = squad_roles(players)
    signed: list[Player] = []
    for player in players:
        key = PlayerId(str(player.id))
        unsigned = player.model_copy(update={"squad_number": numbers[key]})
        contract = contract_for(rng.fork(str(player.id)), unsigned, club_id, roles[key], today)
        with_contract = unsigned.model_copy(update={"contract": contract})
        signed.append(
            with_contract.model_copy(update={"market_value": market_value_of(with_contract, today)})
        )
    return signed


def scale_wages(players: Sequence[Player], target: WageTarget) -> list[Player]:
    """Scale every wage by one factor so the bill lands on ``ratio`` of the weekly budget."""
    raw = sum(p.contract.wage_weekly for p in players if p.contract is not None)
    if raw <= 0:
        return list(players)
    factor = target.budget_weekly * target.ratio / raw
    return [
        p.model_copy(update={"contract": _scaled(p.contract, factor)}) if p.contract else p
        for p in players
    ]


def squad_entries(players: Sequence[Player], club_id: ClubId) -> list[SquadEntry]:
    """The practical club-player links, sorted by shirt number."""
    entries = [
        SquadEntry(
            club_id=club_id,
            player_id=PlayerId(str(p.id)),
            squad_number=p.squad_number or 0,
            status=SquadStatus.YOUTH if p.is_youth else SquadStatus.FIRST_TEAM,
            squad_role=p.contract.squad_role if p.contract else SquadRole.BACKUP,
        )
        for p in players
    ]
    return sorted(entries, key=lambda entry: entry.squad_number)
