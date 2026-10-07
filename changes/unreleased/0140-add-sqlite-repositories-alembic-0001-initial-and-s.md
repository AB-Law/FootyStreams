---
id: 0140
date: 2026-10-07
type: added
scope: [cli]
milestone: M3
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: true
summary: Add SQLite repositories, Alembic 0001_initial and seed --db
---
Adds sqlalchemy>=2.0 and alembic (the design's persistence stack; nothing else). Core tables are built from the same table specs as the in-memory backend, so both pass one contract suite; foreign keys are on, files use WAL, and the ledger and match-event tables refuse UPDATE/DELETE with triggers. Alembic 0001_initial creates 29 tables and the triggers (hand-reviewed autogenerate, split into small functions); tests cover upgrade, downgrade/upgrade and schema parity with the specs (alembic check equivalent). 'uv run seed --db league.sqlite' writes the generated world into SQLite; reading it back equals the world.
