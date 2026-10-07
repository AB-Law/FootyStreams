---
id: 0086
date: 2026-10-07
type: fixed
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Create academy players relative to the rollover date
---
The prospect factory took the world's creation date at construction, so intake after the first season was older than requested and the academy ran dry. The creation date now travels with each create call.
