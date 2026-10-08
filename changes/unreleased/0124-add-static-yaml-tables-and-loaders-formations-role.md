---
id: 0124
date: 2026-10-07
type: added
scope: [data]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Add static YAML tables and loaders: formations, roles, traits, injuries, climate'
---
data/static/{formations,roles,traits,injuries,climate}.yaml with strict validating loaders (seed/static). Roles with several positions expand to one id per position. The SimConfig skeleton from the M2 plan is left to track A (M4 owns SimConfig).
