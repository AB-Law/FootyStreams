"""Behaviour only the SQLite backend has: foreign keys, triggers, stored schema versions."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from footystreams.persistence import codec
from footystreams.persistence.errors import ConflictError, SchemaVersionError
from footystreams.persistence.sql.uow import SqlUnitOfWork
from footystreams.persistence.world_store import load_world, save_world
from tests.contract.conftest import build_backend
from tests.factories.world import make_world

WORLD = make_world(1)


@pytest.fixture(scope="module")
def sql_engine() -> Engine:
    factory, engine = build_backend("sql")
    save_world(WORLD, factory())
    assert engine is not None
    return engine


def test_foreign_keys__a_player_for_an_unknown_club_is_rejected(sql_engine: Engine) -> None:
    player = WORLD.players[0]
    assert player.contract is not None
    orphan = player.model_copy(
        update={
            "id": "plr_orphan",
            "contract": player.contract.model_copy(update={"club_id": "clb_nowhere"}),
        }
    )
    with SqlUnitOfWork(sql_engine) as uow, pytest.raises(ConflictError, match="FOREIGN KEY"):
        uow.players.save(orphan)


def test_foreign_keys__deleting_a_club_that_has_players_is_rejected(sql_engine: Engine) -> None:
    with SqlUnitOfWork(sql_engine) as uow, pytest.raises(ConflictError, match="FOREIGN KEY"):
        uow.clubs.delete(str(WORLD.clubs[0].id))


def test_append_only__the_database_itself_refuses_update_and_delete(sql_engine: Engine) -> None:
    with sql_engine.connect() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(text("UPDATE ledger_entries SET rev = 2"))
        connection.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(text("DELETE FROM ledger_entries"))


def test_schema_version__a_row_from_another_series_cannot_be_read(sql_engine: Engine) -> None:
    key = str(WORLD.referees[0].id)
    with sql_engine.connect() as connection:
        connection.execute(
            text("UPDATE referees SET schema_version = '9.9.0' WHERE id = :k"), {"k": key}
        )
        with SqlUnitOfWork(sql_engine) as uow, pytest.raises(SchemaVersionError, match=r"9\.9\.0"):
            uow.referees.get(key)
        connection.rollback()


def test_schema_version__a_registered_row_migration_upgrades_old_rows(
    sql_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = str(WORLD.referees[0].id)
    monkeypatch.setitem(codec.ROW_MIGRATIONS, ("referees", "9.9.0"), lambda row: row)
    with sql_engine.connect() as connection:
        connection.execute(
            text("UPDATE referees SET schema_version = '9.9.0' WHERE id = :k"), {"k": key}
        )
        connection.commit()
    try:
        with SqlUnitOfWork(sql_engine) as uow:
            assert uow.referees.require(key) == WORLD.referees[0]
    finally:
        with sql_engine.connect() as connection:
            connection.execute(
                text("UPDATE referees SET schema_version = :v WHERE id = :k"),
                {"v": WORLD.referees[0] and "0.2.0", "k": key},
            )
            connection.commit()


def test_file_database__survives_reopening(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from footystreams.persistence.sql.engine import create_sqlite_engine  # noqa: PLC0415
    from footystreams.persistence.sql.migrate import upgrade  # noqa: PLC0415

    path = tmp_path / "league.sqlite"
    first = create_sqlite_engine(path)
    upgrade(first)
    save_world(WORLD, SqlUnitOfWork(first))
    first.dispose()
    second = create_sqlite_engine(path)
    with SqlUnitOfWork(second) as uow:
        assert load_world(uow) == WORLD
