"""Table specs for the league layer: mood, world events, transfers, the ledger and match events."""

from __future__ import annotations

import datetime as dt
from typing import Any

from footystreams.domain.finance import LedgerEntry
from footystreams.domain.mood import StateModifier, WorldEvent
from footystreams.domain.transfer import (
    ContractOffer,
    ScoutReport,
    Transfer,
    TransferBid,
    TransferListing,
    TransferWindow,
)
from footystreams.persistence.records import StageLogEntry, StoredEvent
from footystreams.persistence.spec_model import TableSpec
from footystreams.persistence.spec_model import col as _col


def _expires(modifier: StateModifier) -> dt.date | None:
    return modifier.expires_on


LEAGUE_TABLES: dict[str, TableSpec[Any]] = {
    "modifiers": TableSpec[StateModifier](
        "state_modifiers",
        StateModifier,
        lambda m: str(m.id),
        (
            _col("owner_kind", "str", lambda m: m.owner.kind.value),
            _col("owner_id", "str", lambda m: str(m.owner.id)),
            _col("kind", "str", lambda m: m.kind.value),
            _col("start_on", "date", lambda m: m.start_on),
            _col("expires_on", "date", _expires),
            _col("visibility", "str", lambda m: m.visibility.value),
            _col("origin", "str", lambda m: m.source.origin),
        ),
    ),
    "world_events": TableSpec[WorldEvent](
        "world_events",
        WorldEvent,
        lambda e: str(e.id),
        (
            _col("date", "date", lambda e: e.date),
            _col("kind", "str", lambda e: e.kind),
            _col("visibility", "str", lambda e: e.visibility.value),
            _col("origin", "str", lambda e: e.origin),
        ),
    ),
    "stage_log": TableSpec[StageLogEntry](
        "world_log",
        StageLogEntry,
        lambda r: f"{r.date.isoformat()}:{r.stage}",
        (
            _col("date", "date", lambda r: r.date),
            _col("stage", "str", lambda r: r.stage),
            _col("delta_hash", "str", lambda r: r.delta_hash),
        ),
    ),
    "windows": TableSpec[TransferWindow](
        "transfer_windows",
        TransferWindow,
        lambda w: str(w.id),
        (
            _col("season_id", "str", lambda w: str(w.season_id), "seasons.id"),
            _col("kind", "str", lambda w: w.kind.value),
            _col("opens_on", "date", lambda w: w.opens_on),
            _col("closes_on", "date", lambda w: w.closes_on),
        ),
    ),
    "listings": TableSpec[TransferListing](
        "transfer_listings",
        TransferListing,
        lambda r: str(r.id),
        (
            _col("window_id", "str", lambda r: str(r.window_id), "transfer_windows.id"),
            _col("player_id", "str", lambda r: str(r.player_id), "players.id"),
            _col("club_id", "str", lambda r: str(r.club_id), "clubs.id"),
            _col("asking_price", "int", lambda r: r.asking_price),
        ),
    ),
    "bids": TableSpec[TransferBid](
        "transfer_bids",
        TransferBid,
        lambda r: str(r.id),
        (
            _col("window_id", "str", lambda r: str(r.window_id), "transfer_windows.id"),
            _col("player_id", "str", lambda r: str(r.player_id), "players.id"),
            _col("from_club_id", "str", lambda r: str(r.from_club_id), "clubs.id"),
            _col("to_club_id", "str", lambda r: str(r.to_club_id), "clubs.id"),
            _col("fee", "int", lambda r: r.fee),
            _col("status", "str", lambda r: r.status),
            _col("round", "int", lambda r: r.round),
        ),
    ),
    "offers": TableSpec[ContractOffer](
        "contract_offers",
        ContractOffer,
        lambda r: str(r.id),
        (
            _col(
                "bid_id", "str", lambda r: str(r.bid_id) if r.bid_id else None, "transfer_bids.id"
            ),
            _col("player_id", "str", lambda r: str(r.player_id), "players.id"),
            _col("club_id", "str", lambda r: str(r.club_id), "clubs.id"),
            _col("status", "str", lambda r: r.status),
        ),
    ),
    "transfers": TableSpec[Transfer](
        "transfers",
        Transfer,
        lambda r: str(r.id),
        (
            _col("player_id", "str", lambda r: str(r.player_id), "players.id"),
            _col("from_club_id", "str", lambda r: str(r.from_club_id), "clubs.id"),
            _col("to_club_id", "str", lambda r: str(r.to_club_id), "clubs.id"),
            _col("fee", "int", lambda r: r.fee),
            _col("completed_on", "date", lambda r: r.completed_on),
        ),
    ),
    "scout_reports": TableSpec[ScoutReport](
        "scout_reports",
        ScoutReport,
        lambda r: str(r.id),
        (
            _col("club_id", "str", lambda r: str(r.club_id), "clubs.id"),
            _col("player_id", "str", lambda r: str(r.player_id), "players.id"),
            _col("created_on", "date", lambda r: r.created_on),
        ),
    ),
    "ledger": TableSpec[LedgerEntry](
        "ledger_entries",
        LedgerEntry,
        lambda e: str(e.id),
        (
            _col("club_id", "str", lambda e: str(e.club_id), "clubs.id"),
            _col("date", "date", lambda e: e.date),
            _col("category", "str", lambda e: e.category.value),
            _col("amount", "int", lambda e: e.amount),
            _col("ref_type", "str", lambda e: next(iter(e.ref), None)),
            _col("ref_id", "str", lambda e: next(iter(e.ref.values()), None)),
        ),
        append_only=True,
    ),
    "events": TableSpec[StoredEvent](
        "match_events",
        StoredEvent,
        lambda e: f"{e.match_id}:{e.seq:05d}",
        (
            _col("match_id", "str", lambda e: str(e.match_id), "matches.id"),
            _col("seq", "int", lambda e: e.seq),
            _col("type", "str", lambda e: e.type),
            _col("tick", "int", lambda e: e.tick),
        ),
        append_only=True,
    ),
}
