# ADR 0002: Relational SQL with validated JSON documents for nested data

Status: accepted (2026-10-07). Design reference: `docs/design/04-architecture.md` section 4.

## Context
The domain models are deep (a player has about 120 fields in nested groups). A fully normalised schema
would need hundreds of columns and join tables whose only consumer is Pydantic, and every new field would
need a migration. But the application must still sort, filter and aggregate by match, matchday, date, club,
score, event type and time.

## Decision
- Keep SQLite (SQLAlchemy 2.x, Alembic) behind repository Protocols. This is relational SQL, not NoSQL.
- Every aggregate table has real, indexed columns for identity, foreign keys and anything queried, sorted or
  aggregated, plus a `data` JSON column holding the full Pydantic model, validated on read and write, with a
  per-row `schema_version` and an integer `rev` for optimistic concurrency.
- When a nested field starts to be queried: promote it to a real column (Alembic migration) or add an
  indexed SQLite generated column over `json_extract`; the repository interface does not change.
- Memories, relationships, ledger entries, match events and other growing collections get their own tables.

## Consequences
- Rich models evolve with Pydantic migration functions instead of a migration per field.
- Ad-hoc SQL over nested fields is weaker until a field is promoted.
- Domain code never sees ORM objects; swapping the database later touches only the persistence package.
