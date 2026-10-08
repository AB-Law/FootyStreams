"""Load a market from the repositories, and run one window day end to end."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.mood import StateModifier
from footystreams.domain.player import Player
from footystreams.domain.prospects import ProspectFactory
from footystreams.domain.rng import WorldRng
from footystreams.domain.transfer import TransferWindow
from footystreams.domain.types import ClubId
from footystreams.league.delta import WorldDelta
from footystreams.league.mood import active_modifiers
from footystreams.league.squad import SquadContext, on_budget, rebalance
from footystreams.league.tables import LeagueTables
from footystreams.league.transfer_day import run_market_day
from footystreams.league.transfer_delta import market_delta
from footystreams.league.transfer_market import Market
from footystreams.league.transfer_outside import ensure_outside, top_up_supply, trim_supply
from footystreams.league.transfer_sales import make_listings, outside_bids
from footystreams.league.transfer_windows import days_left
from footystreams.persistence.ports import Repositories

ACTIVE = "active"
FREE_AGENT = "free_agent"


def league_level(repositories: Repositories, players: list[Player]) -> float:
    """The level the league had at its first rollover, or today's mean senior ability."""
    entry = repositories.meta.get("reference_ability")
    if entry is not None:
        return float(entry.value)
    seniors = [p.ability_current for p in players if not p.is_youth and p.contract]
    return sum(seniors) / len(seniors) if seniors else 0.0


def _unhappy(repositories: Repositories, kinds: tuple[str, ...], today: dt.date) -> frozenset[str]:
    found: list[StateModifier] = []
    for kind in kinds:
        found.extend(repositories.modifiers.find({"kind": kind}))
    return frozenset(m.owner.id for m in active_modifiers(found, today))


def load_market(
    repositories: Repositories, window: TransferWindow, today: dt.date, tables: LeagueTables
) -> Market:
    """The window's market as the database stands today."""
    players = [
        *repositories.players.find({"status": ACTIVE}),
        *repositories.players.find({"status": FREE_AGENT}),
    ]
    clubs = {club.id: club for club in repositories.clubs.all()}
    managers = {m.contract.club_id: m for m in repositories.managers.all() if m.contract}
    market = Market(
        window=window,
        today=today,
        players={p.id: p for p in players},
        clubs=clubs,
        staff={cid: repositories.staff.find({"club_id": cid}) for cid in clubs},
        managers=managers,
        entries={cid: repositories.squad_entries.find({"club_id": cid}) for cid in clubs},
        mood=tables.mood,
        level=league_level(repositories, players),
        unhappy=_unhappy(repositories, tables.transfer.sales.unhappy_kinds, today),
    )
    market.listings = {
        listing.player_id: listing
        for listing in repositories.listings.find({"window_id": window.id})
    }
    start, end = window.opens_on, window.closes_on
    for transfer in repositories.transfers.all():
        if start <= transfer.completed_on <= end:
            market.deals[transfer.to_club_id] += 1
    return market


def _scale(market: Market, club_id: ClubId) -> float:
    """How much of the market wage the club can pay: its budget over its bill, at most 1.0."""
    bill = market.wage_bill(club_id)
    budget = market.clubs[club_id].finances.wage_budget_weekly
    return min(1.0, budget / bill) if bill else 1.0


def _final_fill(market: Market, tables: LeagueTables) -> None:
    """On the last day every club is brought to a legal squad from its prospects and free agents."""
    context = SquadContext(market.today, tables.development.squad, tables.development.youth)
    for club_id in market.league_ids():
        pool = sorted(
            (p for p in market.players.values() if p.contract is None), key=lambda p: p.id
        )
        moves = rebalance(club_id, market.seniors(club_id), pool, context)
        for player in (*moves.promoted, *moves.signed):
            market.players[player.id] = on_budget(player, _scale(market, club_id))
        for player in moves.released:
            market.players[player.id] = player
        if moves.promoted or moves.signed or moves.released:
            market.touched.add(club_id)


def run_window_day(
    repositories: Repositories,
    window: TransferWindow,
    context: tuple[dt.date, LeagueTables, ProspectFactory],
    rng: WorldRng,
) -> WorldDelta:
    """One day of an open window as a delta."""
    today, tables, prospects = context
    market = load_market(repositories, window, today, tables)
    originals = dict(market.players)
    ensure_outside(market)
    top_up_supply(market, tables, prospects, rng.fork("supply"))
    make_listings(market, tables)
    run_market_day(market, tables, rng.fork("day"))
    outside_bids(market, tables, rng.fork("outside"))
    if days_left(window, today) == 0:
        _final_fill(market, tables)
        trim_supply(market, tables)
    delta = market_delta(market, originals)
    new_window = () if repositories.windows.get(window.id) else (window,)
    return delta.merge(WorldDelta(windows=new_window))
