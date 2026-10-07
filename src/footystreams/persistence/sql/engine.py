"""Engine creation for SQLite: foreign keys on, WAL for files, one shared connection in memory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

IN_MEMORY = ":memory:"
BUSY_TIMEOUT_MS = 5_000


def sqlite_url(path: str | Path) -> str:
    """SQLAlchemy URL for a database file (or ``:memory:``)."""
    return "sqlite://" if str(path) == IN_MEMORY else f"sqlite:///{path}"


def create_sqlite_engine(path: str | Path = IN_MEMORY) -> Engine:
    """An engine whose connections enforce foreign keys; file databases use WAL."""
    in_memory = str(path) == IN_MEMORY
    engine = (
        create_engine(
            sqlite_url(path), poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        if in_memory
        else create_engine(sqlite_url(path))
    )

    @event.listens_for(engine, "connect")
    def _configure(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        if not in_memory:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine
