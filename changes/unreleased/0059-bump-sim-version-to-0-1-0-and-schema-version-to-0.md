---
id: 0059
date: 2026-10-07
type: changed
scope: [schemas, sim]
milestone: M4
breaking: false
schema_version_impact: patch
sim_version_impact: minor
config_impact: false
migration: false
summary: Bump SIM_VERSION to 0.1.0 and SCHEMA_VERSION to 0.1.3
---
First simulator output: SIM_VERSION 0.0.0 -> 0.1.0. The only schema change is the regenerated default of sim_version/schema_version fields (no field added or removed). The M1 test that pinned the literal constants now checks the semver shape.
