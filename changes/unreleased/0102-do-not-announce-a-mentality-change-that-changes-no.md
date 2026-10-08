---
id: 0102
date: 2026-10-08
type: fixed
scope: [sim]
milestone: M6
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Do not announce a mentality change that changes nothing
---
The manager's mentality shift is skipped when the side is already at the end of the ladder (all out while chasing, ultra defensive while protecting a lead): no tactical_change event naming the unchanged mentality and no cooldown started. Golden digests are unchanged; the unreleased SIM_VERSION 0.3.0 already covers the M6 behaviours.
