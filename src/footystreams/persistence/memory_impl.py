"""Dict-backed implementation of the repository ports (tests, CLI ``--no-db`` and fast league runs).

Rows are encoded and decoded through the same codec as the SQL backend, so a value that would not
survive storage does not survive here either. Decoded rows are cached because they are immutable.
Foreign keys are not enforced; unique columns and append-only tables are.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

from pydantic import BaseModel

from footystreams.domain.versions import SCHEMA_VERSION
from footystreams.persistence.codec import decode, encode
from footystreams.persistence.errors import ConflictError, NotFoundError
from footystreams.persistence.ports import Criteria, UnitOfWork, Versioned
from footystreams.persistence.specs import TABLES, ColumnValue, TableSpec


@dataclass(frozen=True, slots=True)
class _Stored[Row: BaseModel]:
    entity: Row
    values: dict[str, ColumnValue]
    rev: int


Snapshot = dict[str, dict[str, _Stored[Any]]]


class InMemoryDatabase:
    """All tables of an in-memory world; units of work snapshot and restore it."""

    def __init__(self) -> None:
        """Create every table empty."""
        self.tables: Snapshot = {name: {} for name in TABLES}

    def snapshot(self) -> Snapshot:
        """A copy of every table (rows are immutable, so a shallow copy is enough)."""
        return {name: dict(rows) for name, rows in self.tables.items()}

    def restore(self, snapshot: Snapshot) -> None:
        """Replace the contents with an earlier snapshot."""
        self.tables = {name: dict(rows) for name, rows in snapshot.items()}


def _as_int(value: ColumnValue) -> int:
    """An integer column value (None counts as 0); anything else is a programming error."""
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"column value {value!r} is not an integer"
        raise TypeError(msg)
    return value


def _sort_key(value: ColumnValue) -> tuple[bool, Any]:
    return (value is not None, value if value is not None else 0)


class _Table[Row: BaseModel]:
    """Shared read side of the in-memory repositories."""

    def __init__(self, database: InMemoryDatabase, attribute: str) -> None:
        self._database = database
        self._attribute = attribute
        self.spec: TableSpec[Row] = TABLES[attribute]

    @property
    def _rows(self) -> dict[str, _Stored[Row]]:
        return self._database.tables[self._attribute]

    def get(self, key: str) -> Row | None:
        """The row with this key, or None."""
        stored = self._rows.get(key)
        return stored.entity if stored else None

    def all(self) -> list[Row]:
        """Every row, ordered by key."""
        return [self._rows[key].entity for key in sorted(self._rows)]

    def _matching(self, criteria: Criteria | None) -> list[tuple[str, _Stored[Row]]]:
        wanted = dict(criteria or {})
        for name in wanted:
            self.spec.column(name)  # unknown columns raise KeyError, like the SQL backend
        return [
            (key, stored)
            for key, stored in sorted(self._rows.items())
            if all(stored.values[name] == value for name, value in wanted.items())
        ]

    def find(self, criteria: Criteria | None = None, *, order_by: str | None = None) -> list[Row]:
        """Rows matching the criteria, ordered by key or ``order_by``."""
        matching = self._matching(criteria)
        if order_by is not None:
            self.spec.column(order_by)
            matching.sort(key=lambda item: _sort_key(item[1].values[order_by]))
        return [stored.entity for _, stored in matching]

    def count(self, criteria: Criteria | None = None) -> int:
        """How many rows match."""
        return len(self._matching(criteria))

    def total(self, column: str, criteria: Criteria | None = None) -> int:
        """Sum of an integer column over the matching rows."""
        self.spec.column(column)
        return sum(_as_int(stored.values[column]) for _, stored in self._matching(criteria))

    def _encode(self, entity: Row, rev: int) -> _Stored[Row]:
        text = encode(entity)
        key = self.spec.key(entity)
        canonical = decode(
            self.spec.model, text, table=self.spec.name, key=key, stored=SCHEMA_VERSION
        )
        values = {column.name: column.extract(canonical) for column in self.spec.columns}
        return _Stored(canonical, values, rev)

    def _check_unique(self, key: str, stored: _Stored[Row]) -> None:
        groups = [(column.name,) for column in self.spec.columns if column.unique]
        for group in [*groups, *self.spec.unique_together]:
            mine = tuple(stored.values[name] for name in group)
            for other_key, other in self._rows.items():
                if other_key != key and tuple(other.values[name] for name in group) == mine:
                    raise ConflictError(self.spec.name, key, f"{'+'.join(group)} {mine} is taken")


class MemoryRepository[Row: BaseModel](_Table[Row]):
    """Read/write repository over an in-memory table."""

    def require(self, key: str) -> Row:
        """The row with this key; NotFoundError when missing."""
        entity = self.get(key)
        if entity is None:
            raise NotFoundError(self.spec.name, key)
        return entity

    def get_versioned(self, key: str) -> Versioned[Row] | None:
        """The row and its revision, or None."""
        stored = self._rows.get(key)
        return Versioned(stored.entity, stored.rev) if stored else None

    def save(self, entity: Row, *, expected_rev: int | None = None) -> int:
        """Insert or update; ``expected_rev`` enables the optimistic check."""
        key = self.spec.key(entity)
        existing = self._rows.get(key)
        if expected_rev is not None and (existing is None or existing.rev != expected_rev):
            found = "missing" if existing is None else f"rev {existing.rev}"
            raise ConflictError(self.spec.name, key, f"expected rev {expected_rev}, found {found}")
        stored = self._encode(entity, (existing.rev if existing else 0) + 1)
        self._check_unique(key, stored)
        self._rows[key] = stored
        return stored.rev

    def save_many(self, entities: Sequence[Row]) -> None:
        """Insert or update several rows."""
        for entity in entities:
            self.save(entity)

    def delete(self, key: str) -> None:
        """Remove a row; NotFoundError when missing."""
        if key not in self._rows:
            raise NotFoundError(self.spec.name, key)
        del self._rows[key]


class MemoryAppendOnly[Row: BaseModel](_Table[Row]):
    """Append-only repository: rows can be added, never changed or removed."""

    def append(self, entity: Row) -> None:
        """Add a row; a duplicate key raises ConflictError."""
        key = self.spec.key(entity)
        if key in self._rows:
            raise ConflictError(self.spec.name, key, "append-only row already exists")
        stored = self._encode(entity, 1)
        self._check_unique(key, stored)
        self._rows[key] = stored

    def append_many(self, entities: Sequence[Row]) -> None:
        """Add several rows."""
        for entity in entities:
            self.append(entity)


class InMemoryUnitOfWork(UnitOfWork):
    """A transaction over an InMemoryDatabase: snapshot on entry, restore unless committed."""

    def __init__(self, database: InMemoryDatabase) -> None:
        """Create the repositories over ``database``."""
        self.database = database
        self._snapshot: Snapshot | None = None
        self._committed = False
        for attribute, spec in TABLES.items():
            repository: object = (MemoryAppendOnly if spec.append_only else MemoryRepository)(
                database, attribute
            )
            setattr(self, attribute, repository)

    def __enter__(self) -> Self:
        """Begin: remember the current contents."""
        self._snapshot = self.database.snapshot()
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back unless committed."""
        if not self._committed:
            self.rollback()
        self._snapshot = None

    def commit(self) -> None:
        """Keep everything written since entry."""
        self._committed = True
        self._snapshot = self.database.snapshot()

    def rollback(self) -> None:
        """Discard everything written since entry (or the last commit)."""
        if self._snapshot is not None:
            self.database.restore(self._snapshot)
