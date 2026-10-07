"""Turn the market's working state into one ``WorldDelta`` (one transaction)."""

from __future__ import annotations

from footystreams.domain.player import Player
from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.league.delta import WorldDelta
from footystreams.league.ledger import book
from footystreams.league.squad import assign_numbers, squad_entries
from footystreams.league.transfer_market import Market


def market_delta(market: Market, originals: dict[str, Player]) -> WorldDelta:
    """Players that changed, clubs with their money, squad entries, and the day's records."""
    entries = []
    deletions: list[tuple[str, str]] = []
    for club_id in sorted(c for c in market.touched if c != OUTSIDE_WORLD):
        numbered = assign_numbers(market.squad(club_id))
        for player in numbered:
            market.players[player.id] = player
        wanted, stale = squad_entries(club_id, numbered, market.entries.get(club_id, ()))
        entries.extend(wanted)
        deletions.extend(("squad_entries", key) for key in stale)
    money = book(market.clubs, market.postings)
    paid = {club.id: club for club in money.clubs}
    clubs = tuple(paid.get(cid, club) for cid, club in sorted(market.clubs.items()))
    changed = tuple(p for pid, p in sorted(market.players.items()) if originals.get(pid) is not p)
    return WorldDelta(
        players=changed,
        clubs=clubs,
        modifiers=tuple(market.modifiers),
        world_events=tuple(market.events),
        squad_entries=tuple(entries),
        listings=tuple(sorted(market.listings.values(), key=lambda item: item.id)),
        bids=tuple(market.bids),
        offers=tuple(market.offers),
        transfers=tuple(market.transfers),
        ledger=money.ledger,
        deletions=tuple(deletions),
    )
