---
id: 0043
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add SimConfig with config hash and merge, and static formation tables
---
SimConfig starts with model_profile, frame and home-advantage knobs; groups are added by the milestone that needs them. default_tables ships the eight standard formations (YAML loaders arrive with M2).
