"""SQLAlchemy Core repositories over one open connection (one transaction)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection, Select, Table, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.persistence.codec import decode, encode
from footystreams.persistence.errors import ConflictError, NotFoundError
from footystreams.persistence.ports import Criteria, Versioned
from footystreams.persistence.specs import TABLES, TableSpec
from footystreams.persistence.sql.tables import (
    DATA_COLUMN,
    KEY_COLUMN,
    METADATA,
    REV_COLUMN,
    VERSION_COLUMN,
)


class _SqlTable[Row: BaseModel]:
    """Shared read side of the SQL repositories."""

    def __init__(self, connection: Connection, attribute: str) -> None:
        self._connection = connection
        self.spec: TableSpec[Row] = TABLES[attribute]
        self._table: Table = METADATA.tables[self.spec.name]

    def _where[Q: Select[Any]](self, query: Q, criteria: Criteria | None) -> Q:
        for name, value in dict(criteria or {}).items():
            self.spec.column(name)
            column = self._table.c[name]
            query = query.where(column.is_(None) if value is None else column == value)
        return query

    def _decode(self, key: str, text: str, stored_version: str) -> Row:
        return decode(self.spec.model, text, table=self.spec.name, key=key, stored=stored_version)

    def get(self, key: str) -> Row | None:
        """The row with this key, or None."""
        row = self._connection.execute(
            select(self._table.c[DATA_COLUMN], self._table.c[VERSION_COLUMN]).where(
                self._table.c[KEY_COLUMN] == key
            )
        ).first()
        return self._decode(key, row[0], row[1]) if row else None

    def all(self) -> list[Row]:
        """Every row, ordered by key."""
        return self.find()

    def find(self, criteria: Criteria | None = None, *, order_by: str | None = None) -> list[Row]:
        """Rows matching the criteria, ordered by key or ``order_by``."""
        selected = select(
            self._table.c[KEY_COLUMN], self._table.c[DATA_COLUMN], self._table.c[VERSION_COLUMN]
        )
        query = self._where(selected, criteria)
        if order_by is not None:
            self.spec.column(order_by)
            query = query.order_by(self._table.c[order_by])
        rows = self._connection.execute(query.order_by(self._table.c[KEY_COLUMN])).all()
        return [self._decode(str(row[0]), str(row[1]), str(row[2])) for row in rows]

    def count(self, criteria: Criteria | None = None) -> int:
        """How many rows match."""
        query = self._where(select(func.count()).select_from(self._table), criteria)
        return int(self._connection.execute(query).scalar_one())

    def total(self, column: str, criteria: Criteria | None = None) -> int:
        """Sum of an integer column over the matching rows."""
        self.spec.column(column)
        query = select(func.coalesce(func.sum(self._table.c[column]), 0)).select_from(self._table)
        return int(self._connection.execute(self._where(query, criteria)).scalar_one())

    def _values(self, entity: Row, rev: int) -> dict[str, Any]:
        text = encode(entity)
        key = self.spec.key(entity)
        canonical = decode(
            self.spec.model, text, table=self.spec.name, key=key, stored=SCHEMA_VERSION
        )
        values: dict[str, Any] = {
            KEY_COLUMN: key,
            REV_COLUMN: rev,
            VERSION_COLUMN: SCHEMA_VERSION,
            DATA_COLUMN: encode(canonical),
        }
        values.update({column.name: column.extract(canonical) for column in self.spec.columns})
        return values

    def _insert(self, entity: Row, rev: int) -> None:
        values = self._values(entity, rev)
        try:
            self._connection.execute(insert(self._table).values(**values))
        except IntegrityError as error:
            raise ConflictError(self.spec.name, values[KEY_COLUMN], str(error.orig)) from error


class SqlRepository[Row: BaseModel](_SqlTable[Row]):
    """Read/write repository over a SQL table."""

    def require(self, key: str) -> Row:
        """The row with this key; NotFoundError when missing."""
        entity = self.get(key)
        if entity is None:
            raise NotFoundError(self.spec.name, key)
        return entity

    def _current_rev(self, key: str) -> int | None:
        value = self._connection.execute(
            select(self._table.c[REV_COLUMN]).where(self._table.c[KEY_COLUMN] == key)
        ).scalar_one_or_none()
        return None if value is None else int(value)

    def get_versioned(self, key: str) -> Versioned[Row] | None:
        """The row and its revision, or None."""
        entity, rev = self.get(key), self._current_rev(key)
        return None if entity is None or rev is None else Versioned(entity, rev)

    def save(self, entity: Row, *, expected_rev: int | None = None) -> int:
        """Insert or update; ``expected_rev`` enables the optimistic check."""
        key = self.spec.key(entity)
        current = self._current_rev(key)
        if expected_rev is not None and current != expected_rev:
            found = "missing" if current is None else f"rev {current}"
            raise ConflictError(self.spec.name, key, f"expected rev {expected_rev}, found {found}")
        if current is None:
            self._insert(entity, 1)
            return 1
        values = self._values(entity, current + 1)
        try:
            result = self._connection.execute(
                update(self._table)
                .where(self._table.c[KEY_COLUMN] == key, self._table.c[REV_COLUMN] == current)
                .values(**values)
            )
        except IntegrityError as error:
            raise ConflictError(self.spec.name, key, str(error.orig)) from error
        if result.rowcount != 1:
            raise ConflictError(self.spec.name, key, "row changed during the update")
        return current + 1

    def save_many(self, entities: Sequence[Row]) -> None:
        """Insert or update several rows."""
        for entity in entities:
            self.save(entity)

    def delete(self, key: str) -> None:
        """Remove a row; NotFoundError when missing."""
        try:
            result = self._connection.execute(
                delete(self._table).where(self._table.c[KEY_COLUMN] == key)
            )
        except IntegrityError as error:
            raise ConflictError(self.spec.name, key, str(error.orig)) from error
        if result.rowcount != 1:
            raise NotFoundError(self.spec.name, key)


class SqlAppendOnly[Row: BaseModel](_SqlTable[Row]):
    """Append-only repository (the database also blocks UPDATE and DELETE with triggers)."""

    def append(self, entity: Row) -> None:
        """Add a row; a duplicate key raises ConflictError."""
        self._insert(entity, 1)

    def append_many(self, entities: Sequence[Row]) -> None:
        """Add several rows."""
        for entity in entities:
            self.append(entity)
