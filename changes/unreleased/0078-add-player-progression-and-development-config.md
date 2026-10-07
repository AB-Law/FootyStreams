---
id: 0078
date: 2026-10-07
type: added
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add player progression and development config
---
development.yaml holds age curves per attribute group, potential revision, position, retirement, youth and squad parameters. progress_season moves attributes by age curve x headroom x training x playing time x professionalism x development rate with noise, trims gains so ability never exceeds potential, applies injury setbacks, revises potential for young players and journals every point; micro_step does the weekly training gains.
