"""Why clubs sell: surplus players, unhappy players, money trouble, and bids from outside."""

from __future__ import annotations

from footystreams.domain.contract import SquadRole
from footystreams.domain.ids import derive_id
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.transfer import OUTSIDE_WORLD, TransferListing
from footystreams.domain.types import ClubId, Id, PlayerId
from footystreams.domain.valuation import market_value_of
from footystreams.league.contracts import Agreed
from footystreams.league.tables import LeagueTables
from footystreams.league.transfer_day import seller_can_sell
from footystreams.league.transfer_market import Deal, Market, complete
from footystreams.league.transfer_rules import reservation_price

PERCENT = 100.0
UNIT_MAX = 1.0


def _value(player: Player, market: Market) -> int:
    return player.market_value or market_value_of(player, market.today)


def _list(market: Market, player: Player, club_id: ClubId, markup: float) -> None:
    if player.id in market.listings or player.contract is None:
        return
    market.listings[player.id] = TransferListing(
        id=Id(derive_id("listing", market.window.id, player.id)),
        window_id=market.window.id,
        player_id=PlayerId(player.id),
        club_id=club_id,
        asking_price=round(_value(player, market) * markup),
        listed_on=market.today,
    )


def _by_worth(players: list[Player], market: Market) -> list[Player]:
    return sorted(players, key=lambda p: (_value(p, market), p.id))


def make_listings(market: Market, tables: LeagueTables) -> None:
    """List surplus, unhappy and (when the club is in trouble) the most valuable players."""
    sales = tables.transfer.sales
    markup = tables.transfer.window.listing_markup
    for club_id in market.league_ids():
        squad = market.seniors(club_id)
        movable = [p for p in squad if p.contract and p.contract.squad_role is not SquadRole.KEY]
        for player in _by_worth(movable, market)[: max(0, len(squad) - sales.surplus_over)]:
            _list(market, player, club_id, markup)
        for player in squad:
            if player.id in market.unhappy:
                _list(market, player, club_id, markup)
        _list_for_money(market, club_id, movable, (sales.financial_balance_share, markup))


def _list_for_money(
    market: Market, club_id: ClubId, movable: list[Player], terms: tuple[float, float]
) -> None:
    share, markup = terms
    finances = market.clubs[club_id].finances
    deficit = -finances.credit_limit * share - finances.balance
    if deficit <= 0:
        return
    raised = 0
    for player in sorted(movable, key=lambda p: (-_value(p, market), p.id)):
        if raised >= deficit:
            break
        _list(market, player, club_id, markup)
        raised += _value(player, market)


def outside_bids(market: Market, tables: LeagueTables, rng: WorldRng) -> None:
    """Outside clubs bid for the league's best players; the seller accepts a good price."""
    config = tables.transfer.outside
    floor = tables.transfer.valuation.reservation_floor
    for club_id in market.league_ids():
        reputation = market.clubs[club_id].club_reputation
        for player in market.seniors(club_id):
            if (
                player.id in market.sold
                or player.ability_current < config.bid_min_ability * market.level
            ):
                continue
            stream = rng.fork(f"bid:{player.id}")
            if not stream.bernoulli(config.bid_rate * reputation / PERCENT):
                continue
            if player.contract is None or not seller_can_sell(market, club_id, player, tables):
                continue
            fee = round(_value(player, market) * config.bid_premium)
            listing = market.listings.get(player.id)
            wanted = reservation_price(
                _value(player, market),
                player.contract.squad_role,
                listing.asking_price if listing else None,
                (tables.transfer.valuation, False),
            )
            if fee >= wanted * stream.uniform(floor, UNIT_MAX):
                years = stream.fork("years").randint(*tables.transfer.terms.length_years)
                terms = Agreed(player.contract.wage_weekly, years, 1)
                complete(market, Deal(player, OUTSIDE_WORLD, club_id, fee, terms, 1))
