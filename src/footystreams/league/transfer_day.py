"""One window day: clubs with needs shortlist players, bid, agree terms, pass medicals, sign.

Pure given the ``Market`` it is handed and a random stream. Every club decides from what it can
*perceive* of a player (a noisy estimate shaped by its scouting), not from his true ability.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.contract import SquadRole
from footystreams.domain.ids import derive_id
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.staff import StaffRole
from footystreams.domain.transfer import OUTSIDE_WORLD, TransferBid
from footystreams.domain.types import ClubId, Id, PlayerId
from footystreams.domain.valuation import market_value_of
from footystreams.league.contracts import negotiate
from footystreams.league.needs import Need, analyse, group_of
from footystreams.league.scouting import Perception, perceive
from footystreams.league.tables import LeagueTables
from footystreams.league.transfer_market import Deal, Market, complete
from footystreams.league.transfer_rules import (
    FeeAgreed,
    FeeTalks,
    can_afford,
    desire,
    medical_passes,
    negotiate_fee,
    reservation_price,
)
from footystreams.league.transfer_windows import days_left

SHORTLIST = 3
NEEDS_PER_DAY = 2


def judging(market: Market, club_id: ClubId, tables: LeagueTables) -> int:
    """The club's eye for a player: its manager's judgement blended with its scouts'."""
    manager = market.managers.get(club_id)
    base = (
        manager.attributes.judging_ability if manager else tables.transfer.scouting.default_judging
    )
    scouts = [
        s.attrs.scouting_judgement
        for s in market.staff.get(club_id, ())
        if s.role is StaffRole.SCOUT
    ]
    return round((base + sum(scouts) / len(scouts)) / 2) if scouts else base


def seller_can_sell(market: Market, seller: ClubId, player: Player, tables: LeagueTables) -> bool:
    """A club does not sell below its minimum squad or the minimum of the player's position."""
    if seller == OUTSIDE_WORLD:
        return True
    squad = market.seniors(seller)
    group = group_of(player.primary_position)
    in_group = sum(1 for p in squad if group_of(p.primary_position) == group)
    minimum = tables.transfer.needs.position_minimum[group]
    return len(squad) - 1 >= tables.development.squad.min_senior and in_group - 1 >= minimum


def shortlist(
    market: Market, club_id: ClubId, need: Need, tables: LeagueTables, rng: WorldRng
) -> list[tuple[Player, Perception]]:
    """Players the club would consider for the need, best (as it sees them) first."""
    config = tables.transfer
    eyes = judging(market, club_id, tables)
    found: list[tuple[Player, Perception]] = []
    for player in sorted(market.players.values(), key=lambda p: p.id):
        if not _eligible(market, club_id, need, player, tables):
            continue
        view = perceive(player, eyes, config.scouting, rng.fork(f"scout:{player.id}"))
        if view.ability >= need.min_quality:
            found.append((player, view))
    free_first = need.urgency >= 1.0
    found.sort(
        key=lambda item: (item[0].contract is not None and free_first, -item[1].ability, item[0].id)
    )
    return found[:SHORTLIST]


def _eligible(
    market: Market, club_id: ClubId, need: Need, player: Player, tables: LeagueTables
) -> bool:
    if player.is_youth or player.id in market.sold or player.primary_position not in need.positions:
        return False
    if player.age_on(market.today) > tables.transfer.needs.max_age:
        return False
    if player.contract is None:
        return player.status is PlayerStatus.FREE_AGENT
    if player.contract.club_id == club_id or player.status is not PlayerStatus.ACTIVE:
        return False
    return seller_can_sell(market, player.contract.club_id, player, tables)


def _log_bid(market: Market, player: Player, buyer: ClubId, offer: tuple[int, int, str]) -> None:
    """Record a bid that did not end in a transfer (completed ones are recorded by ``complete``)."""
    fee, number, status = offer
    seller = player.contract.club_id if player.contract else OUTSIDE_WORLD
    market.bids.append(
        TransferBid(
            id=Id(derive_id("bid", market.window.id, player.id, buyer)),
            window_id=market.window.id,
            player_id=PlayerId(player.id),
            from_club_id=seller,
            to_club_id=buyer,
            fee=fee,
            round=max(1, min(3, number)),
            status=status,
        )
    )


def _fee(
    market: Market,
    pick: tuple[Player, Perception, Need],
    tables: LeagueTables,
    rng: WorldRng,
) -> FeeAgreed | None:
    player, view, need = pick
    if player.contract is None:
        return FeeAgreed(fee=0, round=1)
    seller = market.clubs[player.contract.club_id]
    listing = market.listings.get(player.id)
    finances = seller.finances
    distressed = (
        finances.balance < -finances.credit_limit * tables.transfer.sales.financial_balance_share
    )
    value = player.market_value or market_value_of(player, market.today)
    talks = FeeTalks(
        market_value=value,
        desire=desire(view, need, player.age_on(market.today), tables.transfer.valuation),
        urgency=need.urgency,
        reservation=reservation_price(
            value,
            player.contract.squad_role if player.contract else SquadRole.BACKUP,
            listing.asking_price if listing else None,
            (tables.transfer.valuation, distressed),
        ),
    )
    return negotiate_fee(talks, tables.transfer.valuation, rng.fork("fee"))


def attempt(
    market: Market,
    club_id: ClubId,
    pick: tuple[Player, Perception, Need],
    tables: LeagueTables,
    rng: WorldRng,
) -> bool:
    """Try to sign one player: fee talks, player terms, affordability, medical. True if signed."""
    player, _, need = pick
    club = market.clubs[club_id]
    agreed = _fee(market, pick, tables, rng)
    if agreed is None:
        _log_bid(market, player, club_id, (0, tables.transfer.valuation.rounds, "rejected"))
        return False
    config = tables.transfer
    terms = negotiate(
        player,
        (club.club_reputation, 1.0),
        (config.terms, config.renewal),
        (market.today, rng.fork("terms"), False),
    )
    if terms is None:
        _log_bid(market, player, club_id, (agreed.fee, agreed.round, "player_refused"))
        return False
    deal = (agreed.fee, terms.wage, market.wage_bill(club_id))
    if not can_afford(club, deal, config.needs, urgent=need.urgency >= 1.0):
        _log_bid(market, player, club_id, (agreed.fee, agreed.round, "unaffordable"))
        return False
    if not medical_passes(player, config.medical, rng.fork("medical")):
        _log_bid(market, player, club_id, (agreed.fee, agreed.round, "failed_medical"))
        return False
    seller = player.contract.club_id if player.contract else None
    complete(market, Deal(player, club_id, seller, agreed.fee, terms, agreed.round))
    return True


@dataclass(frozen=True, slots=True)
class Priority:
    """A club's place in the day's queue."""

    club_id: ClubId
    needs: tuple[Need, ...]

    @property
    def urgency(self) -> float:
        """The strongest need."""
        return self.needs[0].urgency if self.needs else 0.0


def run_market_day(market: Market, tables: LeagueTables, rng: WorldRng) -> None:
    """Let the neediest clubs (all of them in the last days) try to sign a player each."""
    formations = tables.formations.formations
    queue = []
    for club_id in market.league_ids():
        club = market.clubs[club_id]
        needs = analyse(
            market.seniors(club_id),
            formations[club.default_tactics.formation].positions(),
            tables.transfer.needs,
        )
        queue.append(Priority(club_id, tuple(needs)))
    queue.sort(key=lambda item: (-item.urgency, item.club_id))
    panic = days_left(market.window, market.today) <= tables.transfer.window.panic_days
    active = queue if panic else queue[: tables.transfer.window.buyers_per_day]
    for item in active:
        if market.deals[item.club_id] >= tables.transfer.window.deals_per_club:
            continue
        _sign_one(market, item, tables, rng.fork(f"club:{item.club_id}"))


def _sign_one(market: Market, item: Priority, tables: LeagueTables, rng: WorldRng) -> None:
    for need in item.needs[:NEEDS_PER_DAY]:
        for player, view in shortlist(market, item.club_id, need, tables, rng.fork(need.group)):
            if attempt(
                market, item.club_id, (player, view, need), tables, rng.fork(f"try:{player.id}")
            ):
                return
