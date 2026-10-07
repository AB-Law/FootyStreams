---
id: 0043
date: 2026-10-07
type: added
scope: [schemas]
milestone: M2
breaking: false
schema_version_impact: minor
sim_version_impact: none
config_impact: false
migration: false
summary: Add world record and static-table models
---
Additive only: Nation, City, SquadEntry, WorldManifest, Formation(+slots, catalog), TraitDefinition, InjuryType (+ catalogs) and the in-memory World bundle. No existing model changed. SCHEMA_VERSION 0.2.0 -> 0.3.0 after Track A took 0.2.0 for M7 (flagged: this is the only contract touch in track B so far). Needed in domain because persistence and league may import only domain.
