"""Table specifications: one declarative description per stored model.

A spec says which model a table stores, how to derive its key, and which queryable columns exist
(everything the league filters, sorts or sums by is a real column; the rest stays in the JSON
document). Both repository implementations and the SQL schema are built from these specs, so the
in-memory and SQLite backends cannot drift apart.
"""

from __future__ import annotations

from typing import Any

from footystreams.persistence.spec_model import Column, ColumnType, ColumnValue, TableSpec
from footystreams.persistence.specs_core import CORE_TABLES
from footystreams.persistence.specs_league import LEAGUE_TABLES

TABLES: dict[str, TableSpec[Any]] = {**CORE_TABLES, **LEAGUE_TABLES}

__all__ = ["TABLES", "Column", "ColumnType", "ColumnValue", "TableSpec"]
