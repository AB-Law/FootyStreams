"""Codec round trips and Alembic migrations."""

from __future__ import annotations

from sqlalchemy import inspect, text

from footystreams.persistence.specs import TABLES
from footystreams.persistence.sql.engine import create_sqlite_engine
from footystreams.persistence.sql.migrate import downgrade, schema_differences, upgrade


def test_migration__upgrade_creates_every_table_and_matches_the_specs() -> None:
    engine = create_sqlite_engine()
    upgrade(engine)
    tables = set(inspect(engine).get_table_names())
    assert {spec.name for spec in TABLES.values()} <= tables
    assert "alembic_version" in tables
    assert schema_differences(engine) == []


def test_migration__downgrade_then_upgrade_round_trips() -> None:
    engine = create_sqlite_engine()
    upgrade(engine)
    downgrade(engine)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    upgrade(engine)
    assert schema_differences(engine) == []


def test_migration__foreign_keys_are_enforced_on_every_connection() -> None:
    engine = create_sqlite_engine()
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_migration__upgrade_is_idempotent_at_head() -> None:
    engine = create_sqlite_engine()
    upgrade(engine)
    upgrade(engine)
    assert schema_differences(engine) == []
