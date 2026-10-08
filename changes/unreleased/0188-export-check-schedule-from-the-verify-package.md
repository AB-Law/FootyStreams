---
id: 0188
date: 2026-10-08
type: fixed
scope: [verify]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Export check_schedule from the verify package
---
W12 lived in verify.schedule but was not re-exported from the package surface alongside the other league/world checks.
