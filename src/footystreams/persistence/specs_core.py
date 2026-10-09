"""Table specs for the world itself: people, clubs, competitions, fixtures, matches."""

from __future__ import annotations

from typing import Any

from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.fixture import Fixture
from footystreams.domain.manager import Manager
from footystreams.domain.match import Match
from footystreams.domain.media import MediaPersonality
from footystreams.domain.memory import MemoryRecord
from footystreams.domain.player import Player
from footystreams.domain.proposals import Proposal
from footystreams.domain.referee import Referee
from footystreams.domain.relationship import Relationship
from footystreams.domain.staff import StaffMember
from footystreams.domain.world import City, Nation, SquadEntry, WiderClub
from footystreams.persistence.records import (
    MetaEntry,
    StandingsSnapshot,
    SummaryRecord,
)
from footystreams.persistence.spec_model import Column, TableSpec
from footystreams.persistence.spec_model import col as _col


def _contract_club(player: Player) -> str | None:
    return str(player.contract.club_id) if player.contract else None


def _wage(player: Player) -> int:
    return player.contract.wage_weekly if player.contract else 0


def _manager_club(manager: Manager) -> str | None:
    return str(manager.contract.club_id) if manager.contract else None


def _player_columns() -> tuple[Column[Player], ...]:
    return (
        _col("club_id", "str", _contract_club, "clubs.id"),
        _col("primary_position", "str", lambda p: p.primary_position.value),
        _col("ability_current", "int", lambda p: p.ability_current),
        _col("date_of_birth", "date", lambda p: p.date_of_birth),
        _col("squad_status", "str", lambda p: p.squad_status.value),
        _col("status", "str", lambda p: p.status.value),
        _col("injured", "bool", lambda p: p.current_injury is not None),
        _col("suspended", "bool", lambda p: p.suspension is not None),
        _col("market_value", "int", lambda p: p.market_value),
        _col("wage_weekly", "int", _wage),
    )


def _fixture_columns() -> tuple[Column[Fixture], ...]:
    return (
        _col("season_id", "str", lambda f: str(f.season_id), "seasons.id"),
        _col("competition_id", "str", lambda f: str(f.competition_id), "competitions.id"),
        _col("matchday", "int", lambda f: f.matchday),
        _col("date", "date", lambda f: f.date),
        _col("home_club_id", "str", lambda f: str(f.home_club_id), "clubs.id"),
        _col("away_club_id", "str", lambda f: str(f.away_club_id), "clubs.id"),
        _col("status", "str", lambda f: f.status.value),
        _col("match_id", "str", lambda f: str(f.match_id) if f.match_id else None),
    )


def _match_columns() -> tuple[Column[Match], ...]:
    return (
        _col("fixture_id", "str", lambda m: str(m.fixture_id), "fixtures.id"),
        _col("season_id", "str", lambda m: str(m.season_id), "seasons.id"),
        _col("matchday", "int", lambda m: m.matchday),
        _col("date", "date", lambda m: m.date),
        _col("home_club_id", "str", lambda m: str(m.home_club_id), "clubs.id"),
        _col("away_club_id", "str", lambda m: str(m.away_club_id), "clubs.id"),
        _col("seed", "int", lambda m: m.seed),
        _col("config_hash", "str", lambda m: m.config_hash),
        _col("sim_version", "str", lambda m: m.sim_version),
        _col("status", "str", lambda m: m.status.value),
        _col("home_goals", "int", lambda m: m.home_goals),
        _col("away_goals", "int", lambda m: m.away_goals),
        _col("log_digest", "str", lambda m: m.log_digest),
    )


CORE_TABLES: dict[str, TableSpec[Any]] = {
    "meta": TableSpec[MetaEntry]("world_meta", MetaEntry, lambda r: r.key),
    "nations": TableSpec[Nation](
        "nations",
        Nation,
        lambda n: str(n.id),
        (_col("name", "str", lambda n: n.name), _col("is_home", "bool", lambda n: n.is_home)),
    ),
    "cities": TableSpec[City](
        "cities",
        City,
        lambda c: str(c.id),
        (
            _col("nation_id", "str", lambda c: str(c.nation_id), "nations.id"),
            _col("name", "str", lambda c: c.name),
            _col("climate", "str", lambda c: c.climate),
        ),
    ),
    "competitions": TableSpec[Competition](
        "competitions", Competition, lambda c: str(c.id), (_col("name", "str", lambda c: c.name),)
    ),
    "seasons": TableSpec[Season](
        "seasons",
        Season,
        lambda s: str(s.id),
        (
            _col("competition_id", "str", lambda s: str(s.competition_id), "competitions.id"),
            _col("label", "str", lambda s: s.label),
            _col("starts_on", "date", lambda s: s.starts_on),
        ),
    ),
    "clubs": TableSpec[Club](
        "clubs",
        Club,
        lambda c: str(c.id),
        (
            _col("short_code", "str", lambda c: c.short_code, unique=True),
            _col("name", "str", lambda c: c.name),
            _col("reputation", "int", lambda c: c.club_reputation),
            _col("balance", "int", lambda c: c.finances.balance),
            _col("nation_id", "str", lambda c: str(c.location.nation_id), "nations.id"),
        ),
    ),
    "wider_clubs": TableSpec[WiderClub](
        "wider_clubs",
        WiderClub,
        lambda c: str(c.id),
        (
            _col("name", "str", lambda c: c.name),
            _col("city", "str", lambda c: c.city),
            _col("region", "str", lambda c: c.region),
        ),
    ),
    "players": TableSpec[Player]("players", Player, lambda p: str(p.id), _player_columns()),
    "squad_entries": TableSpec[SquadEntry](
        "squad_entries",
        SquadEntry,
        lambda e: f"{e.club_id}:{e.player_id}",
        (
            _col("club_id", "str", lambda e: str(e.club_id), "clubs.id"),
            _col("player_id", "str", lambda e: str(e.player_id), "players.id"),
            _col("squad_number", "int", lambda e: e.squad_number),
            _col("status", "str", lambda e: e.status.value),
        ),
        unique_together=(("club_id", "squad_number"),),
    ),
    "managers": TableSpec[Manager](
        "managers",
        Manager,
        lambda m: str(m.id),
        (
            _col("club_id", "str", _manager_club, "clubs.id"),
            _col("reputation", "int", lambda m: m.reputation),
        ),
    ),
    "staff": TableSpec[StaffMember](
        "staff",
        StaffMember,
        lambda s: str(s.id),
        (
            _col("club_id", "str", lambda s: str(s.club_id), "clubs.id"),
            _col("role", "str", lambda s: s.role.value),
            _col("reputation", "int", lambda s: s.reputation),
        ),
    ),
    "referees": TableSpec[Referee](
        "referees",
        Referee,
        lambda r: str(r.id),
        (_col("reputation", "int", lambda r: r.reputation),),
    ),
    "media": TableSpec[MediaPersonality](
        "media_personalities",
        MediaPersonality,
        lambda m: str(m.id),
        (_col("role", "str", lambda m: m.role.value),),
    ),
    "fixtures": TableSpec[Fixture]("fixtures", Fixture, lambda f: str(f.id), _fixture_columns()),
    "matches": TableSpec[Match]("matches", Match, lambda m: str(m.id), _match_columns()),
    "summaries": TableSpec[SummaryRecord](
        "match_summaries",
        SummaryRecord,
        lambda r: str(r.match_id),
        (_col("match_id", "str", lambda r: str(r.match_id), "matches.id"),),
    ),
    "standings": TableSpec[StandingsSnapshot](
        "standings_snapshots",
        StandingsSnapshot,
        lambda r: f"{r.season_id}:{r.after_matchday:03d}",
        (
            _col("season_id", "str", lambda r: str(r.season_id), "seasons.id"),
            _col("after_matchday", "int", lambda r: r.after_matchday),
        ),
    ),
    "relationships": TableSpec[Relationship](
        "relationships",
        Relationship,
        lambda r: str(r.id),
        (
            _col("a_kind", "str", lambda r: r.a.kind.value),
            _col("a_id", "str", lambda r: str(r.a.id)),
            _col("b_kind", "str", lambda r: r.b.kind.value),
            _col("b_id", "str", lambda r: str(r.b.id)),
            _col("kind", "str", lambda r: r.kind),
            _col("strength", "float", lambda r: r.strength),
        ),
    ),
    "memories": TableSpec[MemoryRecord](
        "memories",
        MemoryRecord,
        lambda m: str(m.id),
        (
            _col("owner_kind", "str", lambda m: m.owner.kind.value),
            _col("owner_id", "str", lambda m: str(m.owner.id)),
            _col("kind", "str", lambda m: m.kind),
            _col("created_on", "date", lambda m: m.created_on),
        ),
    ),
    "proposals": TableSpec[Proposal](
        "proposals",
        Proposal,
        lambda p: str(p.id),
        (
            _col("kind", "str", lambda p: p.kind),
            _col("status", "str", lambda p: p.status.value),
            _col("created_on", "date", lambda p: p.created_on),
        ),
    ),
}
