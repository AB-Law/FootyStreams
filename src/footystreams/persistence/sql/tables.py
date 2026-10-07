"""SQLAlchemy Core tables built from the table specs (the single source of the schema)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import TypeEngine

from footystreams.persistence.specs import TABLES, ColumnType, TableSpec

KEY_COLUMN = "id"
REV_COLUMN = "rev"
VERSION_COLUMN = "schema_version"
DATA_COLUMN = "data"
SQL_TYPES: dict[ColumnType, type[TypeEngine[Any]]] = {
    "str": String,
    "int": Integer,
    "float": Float,
    "bool": Boolean,
    "date": Date,
}
# Indexes beyond one per foreign key: the access paths the league actually uses.
EXTRA_INDEXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "ledger_entries": (("club_id", "date"),),
    "fixtures": (("season_id", "matchday"),),
    "match_events": (("match_id", "type"),),
    "players": (("squad_status",), ("status",)),
    "relationships": (("a_kind", "a_id"), ("b_kind", "b_id")),
    "state_modifiers": (("owner_kind", "owner_id"),),
    "world_events": (("date",),),
}
APPEND_ONLY_TRIGGERS = ("UPDATE", "DELETE")


def _table(metadata: MetaData, spec: TableSpec[Any]) -> Table:
    columns: list[Column[Any]] = [
        Column(KEY_COLUMN, String, primary_key=True),
        Column(REV_COLUMN, Integer, nullable=False),
        Column(VERSION_COLUMN, String, nullable=False),
        Column(DATA_COLUMN, Text, nullable=False),
    ]
    for column in spec.columns:
        target = ForeignKey(column.references) if column.references else None
        args = [target] if target else []
        columns.append(Column(column.name, SQL_TYPES[column.type], *args, nullable=True))
    constraints: list[UniqueConstraint] = [
        UniqueConstraint(*group, name=f"uq_{spec.name}_{'_'.join(group)}")
        for group in [*((c.name,) for c in spec.columns if c.unique), *spec.unique_together]
    ]
    table = Table(spec.name, metadata, *columns, *constraints)
    indexed = [(c.name,) for c in spec.columns if c.references]
    for group in [*indexed, *EXTRA_INDEXES.get(spec.name, ())]:
        Index(f"ix_{spec.name}_{'_'.join(group)}", *(table.c[name] for name in group))
    return table


def build_metadata() -> MetaData:
    """The full schema: one table per spec."""
    metadata = MetaData()
    for spec in TABLES.values():
        _table(metadata, spec)
    return metadata


METADATA = build_metadata()


def append_only_tables() -> tuple[str, ...]:
    """Names of tables that get UPDATE/DELETE-blocking triggers."""
    return tuple(spec.name for spec in TABLES.values() if spec.append_only)


def trigger_statements(table: str) -> tuple[str, ...]:
    """SQLite statements that make ``table`` append-only."""
    return tuple(
        f"CREATE TRIGGER trg_{table}_no_{action.lower()} BEFORE {action} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        for action in APPEND_ONLY_TRIGGERS
    )
