"""Run Alembic migrations programmatically (used by the CLIs and the tests)."""

from __future__ import annotations

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine

from alembic import command
from footystreams.persistence.sql.tables import METADATA

PROJECT_ROOT = Path(__file__).resolve().parents[4]
HEAD = "head"
BASE = "base"


def _config(connection_holder: dict[str, object]) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.attributes.update(connection_holder)
    return config


def upgrade(engine: Engine, revision: str = HEAD) -> None:
    """Bring the database to ``revision`` (default: the latest)."""
    with engine.begin() as connection:
        command.upgrade(_config({"connection": connection}), revision)


def downgrade(engine: Engine, revision: str = BASE) -> None:
    """Roll the database back to ``revision`` (default: empty)."""
    with engine.begin() as connection:
        command.downgrade(_config({"connection": connection}), revision)


def schema_differences(engine: Engine) -> list[object]:
    """What `alembic check` would report: differences between the database and the table specs."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return list(compare_metadata(context, METADATA))
