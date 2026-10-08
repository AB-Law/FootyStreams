"""Rollover steps about people and squads: academy intake, the free-agent pool, squads."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.prospects import ProspectRequest
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Position
from footystreams.league.retirement import retired, retirement_news
from footystreams.league.rollover_state import (
    RolloverData,
    RolloverServices,
    Work,
    seniors_of,
    wage_scale,
)
from footystreams.league.squad import (
    SquadContext,
    assign_numbers,
    on_budget,
    rebalance,
    squad_entries,
    squad_value,
)
from footystreams.league.tables import LeagueTables
from footystreams.league.youth import intake_requests, signed_prospect

FREE_AGENT_REPUTATION = 30


def mean_ability(players: Sequence[Player]) -> float:
    """Mean current ability of the active senior players."""
    seniors = [
        p.ability_current for p in players if not p.is_youth and p.status is PlayerStatus.ACTIVE
    ]
    return sum(seniors) / len(seniors) if seniors else 0.0


def _formation_positions(tables: LeagueTables, club: Club) -> list[Position]:
    return list(tables.formations.formations[club.default_tactics.formation].positions())


def _create(
    work: Work,
    data: RolloverData,
    requests: Sequence[ProspectRequest],
    context: tuple[RolloverServices, dt.date, WorldRng],
) -> list[Player]:
    services, today, rng = context
    known = [*work.players.values(), *data.retired_names]
    return services.prospects.create(requests, known, (today, rng))


def intake(
    work: Work,
    data: RolloverData,
    context: tuple[RolloverServices, dt.date],
    rng: WorldRng,
) -> None:
    """The academy intake of every club, signed on youth contracts."""
    services, today = context
    youth = services.tables.development.youth
    mean = work.reference
    key = str(data.season.starts_on.year + 1)
    requests: list[ProspectRequest] = []
    for club_id in sorted(work.clubs):
        club = work.clubs[club_id]
        shape = (_formation_positions(services.tables, club), mean)
        requests.extend(intake_requests(club, shape, key, youth, rng.fork(f"intake:{club_id}")))
    for request, player in zip(
        requests, _create(work, data, requests, (services, today, rng.fork("create"))), strict=True
    ):
        if request.club_id is not None:
            work.players[player.id] = signed_prospect(player, request.club_id, today, youth)


def top_up_pool(
    work: Work, data: RolloverData, context: tuple[RolloverServices, dt.date], rng: WorldRng
) -> None:
    """Journeymen join the free-agent pool until it has the configured size."""
    services, today = context
    config = services.tables.development.squad
    free = sum(1 for p in work.players.values() if p.status is PlayerStatus.FREE_AGENT)
    missing = max(0, config.free_agent_pool - free)
    positions = [Position.GK, Position.CB, Position.RB, Position.CM, Position.RW, Position.ST]
    mean = work.reference
    key = f"pool:{data.season.starts_on.year + 1}"
    requests = [
        ProspectRequest(
            key=f"{key}:{index}",
            position=positions[index % len(positions)],
            age=rng.fork(f"age:{index}").randint(*config.journeyman_age),
            ability=round(mean * config.journeyman_ability_fraction),
            potential_bonus=0,
            region=next(iter(work.clubs.values())).location.region,
            club_reputation=FREE_AGENT_REPUTATION,
            club_id=None,
            youth=False,
        )
        for index in range(missing)
    ]
    for player in _create(work, data, requests, (services, today, rng.fork("create"))):
        work.players[player.id] = player


def trim_pool(work: Work, context: tuple[RolloverServices, dt.date]) -> None:
    """The weakest unsigned players beyond the pool limit leave the game."""
    services, today = context
    limit = services.tables.development.squad.free_agent_pool_max
    weight = services.tables.development.youth.potential_weight
    free = sorted(
        (p for p in work.players.values() if p.status is PlayerStatus.FREE_AGENT),
        key=lambda p: (-squad_value(p, weight), p.id),
    )
    for player in free[limit:]:
        work.players[player.id] = retired(player, today)
        work.events.append(retirement_news(player, today, "left_the_game"))


def squads(work: Work, data: RolloverData, context: tuple[RolloverServices, dt.date]) -> None:
    """Rebalance every club's squad, then number the newcomers and sync the squad entries."""
    services, today = context
    squad_context = SquadContext(
        today, services.tables.development.squad, services.tables.development.youth
    )
    for club_id in sorted(work.clubs):
        pool = sorted(
            (p for p in work.players.values() if p.status is PlayerStatus.FREE_AGENT),
            key=lambda p: p.id,
        )
        members = seniors_of(work, club_id)
        scale = min(1.0, wage_scale(work, club_id, services.tables.development.rollover))
        moves = rebalance(club_id, members, pool, squad_context)
        for player in (*moves.promoted, *moves.signed):
            work.players[player.id] = on_budget(player, scale)
        for player in moves.released:
            work.players[player.id] = player
        final = assign_numbers(seniors_of(work, club_id))
        for player in final:
            work.players[player.id] = player
        wanted, stale = squad_entries(club_id, final, data.entries.get(club_id, ()))
        work.entries.extend(wanted)
        work.deletions.extend(("squad_entries", key) for key in stale)
