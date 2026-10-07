"""The declarative description of a stored table: columns, keys and constraints."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

ColumnType = Literal["str", "int", "float", "bool", "date"]
ColumnValue = str | int | float | bool | dt.date | None


@dataclass(frozen=True, slots=True)
class Column[Row]:
    """A queryable column derived from a stored model."""

    name: str
    type: ColumnType
    extract: Callable[[Row], ColumnValue]
    references: str | None = None  # "table.column" foreign key
    unique: bool = False


@dataclass(frozen=True, slots=True)
class TableSpec[Row: BaseModel]:
    """How one model is stored."""

    name: str
    model: type[Row]
    key: Callable[[Row], str]
    columns: tuple[Column[Row], ...] = ()
    unique_together: tuple[tuple[str, ...], ...] = ()
    append_only: bool = False

    def column(self, name: str) -> Column[Row]:
        """Look up a declared column; unknown names are programming errors."""
        for column in self.columns:
            if column.name == name:
                return column
        msg = f"table {self.name!r} has no column {name!r}"
        raise KeyError(msg)


def col[Row](
    name: str,
    type_: ColumnType,
    extract: Callable[[Row], ColumnValue],
    references: str | None = None,
    *,
    unique: bool = False,
) -> Column[Row]:
    """Shorthand for a Column."""
    return Column(name, type_, extract, references, unique)
