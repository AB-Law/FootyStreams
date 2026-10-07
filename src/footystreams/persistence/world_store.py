"""Save a generated World into a database and load it back (the ``seed --db`` path)."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION
from footystreams.domain.world import World
from footystreams.persistence.errors import NotFoundError
from footystreams.persistence.ports import Repositories, UnitOfWork
from footystreams.persistence.records import MetaEntry

KEY_WORLD_SEED = "world_seed"
KEY_CREATED = "created_in_world"
KEY_CURRENT_DATE = "current_date"
KEY_SCHEMA_VERSION = "schema_version"
KEY_SIM_VERSION = "sim_version"
KEY_CONFIG_HASH = "config_hash"
NO_CONFIG = "none"


def save_world(world: World, uow: UnitOfWork) -> None:
    """Write the whole world in foreign-key order and commit (one transaction)."""
    with uow:
        uow.nations.save_many(world.nations)
        uow.cities.save_many(world.cities)
        uow.clubs.save_many(world.clubs)
        uow.competitions.save_many(world.competitions)
        uow.seasons.save_many(world.seasons)
        uow.players.save_many(world.players)
        uow.squad_entries.save_many(world.squad_entries)
        uow.managers.save_many(world.managers)
        uow.staff.save_many(world.staff)
        uow.referees.save_many(world.referees)
        uow.media.save_many(world.media)
        uow.relationships.save_many(world.relationships)
        uow.memories.save_many(world.memories)
        uow.ledger.append_many(world.ledger_opening)
        _write_meta(world, uow)
        uow.commit()


def _write_meta(world: World, uow: UnitOfWork) -> None:
    entries = {
        KEY_WORLD_SEED: str(world.world_seed),
        KEY_CREATED: world.created_in_world.isoformat(),
        KEY_CURRENT_DATE: world.created_in_world.isoformat(),
        KEY_SCHEMA_VERSION: SCHEMA_VERSION,
        KEY_SIM_VERSION: SIM_VERSION,
        KEY_CONFIG_HASH: NO_CONFIG,
    }
    uow.meta.save_many([MetaEntry(key=key, value=value) for key, value in entries.items()])


def read_meta(repositories: Repositories, key: str) -> str:
    """One world_meta value; raises NotFoundError when the database holds no such key."""
    entry = repositories.meta.get(key)
    if entry is None:
        raise NotFoundError("world_meta", key)
    return entry.value


def load_world(repositories: Repositories) -> World:
    """Rebuild the World that ``save_world`` stored (same ordering as the generator)."""
    return World(
        world_seed=int(read_meta(repositories, KEY_WORLD_SEED)),
        created_in_world=dt.date.fromisoformat(read_meta(repositories, KEY_CREATED)),
        nations=tuple(repositories.nations.all()),
        cities=tuple(repositories.cities.all()),
        competitions=tuple(repositories.competitions.all()),
        seasons=tuple(repositories.seasons.all()),
        clubs=tuple(repositories.clubs.all()),
        squad_entries=tuple(
            sorted(repositories.squad_entries.all(), key=lambda e: (e.club_id, e.squad_number))
        ),
        players=tuple(repositories.players.all()),
        managers=tuple(repositories.managers.all()),
        staff=tuple(repositories.staff.all()),
        referees=tuple(repositories.referees.all()),
        media=tuple(repositories.media.all()),
        relationships=tuple(repositories.relationships.all()),
        memories=tuple(repositories.memories.all()),
        ledger_opening=tuple(repositories.ledger.all()),
    )
