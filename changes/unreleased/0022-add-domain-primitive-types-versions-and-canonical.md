---
id: 0022
date: 2026-10-07
type: added
scope: [domain]
milestone: M1
breaking: false
schema_version_impact: minor
sim_version_impact: none
config_impact: false
migration: false
summary: Add domain primitive types, versions and canonical JSON
---
Introduce frozen DomainModel base, id/scale primitives, enums, Pos/EntityRef, SCHEMA_VERSION/SIM_VERSION in domain.versions, and canonical_json. Pydantic v2 is the first runtime dependency beyond PyYAML.
