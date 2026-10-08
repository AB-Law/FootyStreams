"""Unit of work over a SQLAlchemy engine: one connection, one transaction."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import Connection, Engine
from sqlalchemy.engine.base import RootTransaction

from footystreams.persistence.ports import UnitOfWork
from footystreams.persistence.specs import TABLES
from footystreams.persistence.sql.repos import SqlAppendOnly, SqlRepository


class SqlUnitOfWork(UnitOfWork):
    """A transaction over all repositories; commits only when ``commit`` is called."""

    def __init__(self, engine: Engine) -> None:
        """Remember the engine; the connection is opened on ``__enter__``."""
        self._engine = engine
        self._connection: Connection | None = None
        self._transaction: RootTransaction | None = None

    def __enter__(self) -> Self:
        """Open a connection and begin a transaction; build the repositories on it."""
        self._connection = self._engine.connect()
        self._transaction = self._connection.begin()
        for attribute, spec in TABLES.items():
            repository: object = (SqlAppendOnly if spec.append_only else SqlRepository)(
                self._connection, attribute
            )
            setattr(self, attribute, repository)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back unless committed, then release the connection."""
        try:
            if self._transaction is not None and self._transaction.is_active:
                self._transaction.rollback()
        finally:
            if self._connection is not None:
                self._connection.close()
            self._connection = self._transaction = None

    def commit(self) -> None:
        """Commit and start a fresh transaction so the block can keep working."""
        if self._connection is None or self._transaction is None:
            msg = "commit outside a unit-of-work block"
            raise RuntimeError(msg)
        self._transaction.commit()
        self._transaction = self._connection.begin()

    def rollback(self) -> None:
        """Roll back everything since the last commit and start a fresh transaction."""
        if self._connection is None or self._transaction is None:
            msg = "rollback outside a unit-of-work block"
            raise RuntimeError(msg)
        self._transaction.rollback()
        self._transaction = self._connection.begin()
