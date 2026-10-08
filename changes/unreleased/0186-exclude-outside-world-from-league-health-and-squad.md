---
id: 0186
date: 2026-10-08
type: fixed
scope: [league]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Exclude OUTSIDE_WORLD from league health and squad checks
---
Health metrics and squad/long-run checks were counting the synthetic outside club and its supply, so L04 could pass by coincidence and league means were diluted.
