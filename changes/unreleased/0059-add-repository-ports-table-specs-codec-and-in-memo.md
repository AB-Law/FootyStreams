---
id: 0059
date: 2026-10-07
type: added
scope: [persistence]
milestone: M3
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add repository ports, table specs, codec and in-memory repositories
---
persistence/ports.py defines Repository, AppendOnlyRepository, UnitOfWork and WorldReader (the only persistence module league may import). specs.py describes 30 tables declaratively (key, queryable columns, foreign keys, unique sets, append-only); the in-memory backend, the SQL backend and the migrations are all built from it. The codec checks the stored schema_version on read and applies registered row migrations. Optimistic concurrency: save(expected_rev=...) raises ConflictError. The contract suite (tests/contract) runs every behaviour against each backend.
