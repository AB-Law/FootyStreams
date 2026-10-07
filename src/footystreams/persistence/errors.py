"""Persistence errors; each message carries the table and key involved."""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Base class of every persistence failure."""


class NotFoundError(PersistenceError):
    """A required row does not exist."""

    def __init__(self, table: str, key: str) -> None:
        """Record which row was missing."""
        super().__init__(f"{table}: no row with key {key!r}")
        self.table = table
        self.key = key


class ConflictError(PersistenceError):
    """An optimistic-concurrency check failed (the row changed, or exists or is missing)."""

    def __init__(self, table: str, key: str, detail: str) -> None:
        """Record which row conflicted and why."""
        super().__init__(f"{table}: conflict on key {key!r}: {detail}")
        self.table = table
        self.key = key


class SchemaVersionError(PersistenceError):
    """A stored row was written under a schema version this code cannot read."""

    def __init__(self, table: str, key: str, stored: str, current: str) -> None:
        """Record the stored and the current schema versions."""
        super().__init__(
            f"{table}: row {key!r} has schema version {stored}, this code reads {current}"
        )
        self.table = table
        self.key = key


class AppendOnlyError(PersistenceError):
    """An attempt to change or delete a row of an append-only table."""
