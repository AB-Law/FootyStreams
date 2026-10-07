---
id: 0146
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add WorldDelta and stateless derived ids
---
WorldDelta is the write-set every pure league stage returns (hashable by content, applied through the repository ports). derive_id mints ids from what a row is about so re-running a stage yields the same rows.
