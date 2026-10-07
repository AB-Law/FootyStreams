---
id: 0038
date: 2026-10-08
type: added
scope: [tools]
milestone: M1
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Enforce SCHEMA_VERSION bump when schemas change
---
Thread base/head SCHEMA_VERSION via git into SchemaVersionFact; when schemas/ changes require impact and a version bump (or first introduction).
