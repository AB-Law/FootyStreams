---
id: 0036
date: 2026-10-08
type: added
scope: [domain, cli, schemas]
milestone: M1
breaking: false
schema_version_impact: minor
sim_version_impact: none
config_impact: false
migration: false
summary: Add usage registry and export-schemas with drift test
---
Usage registry, export-schemas CLI, drift test, and VoiceCasting.voice_register rename so the field does not shadow DomainModel.register.
