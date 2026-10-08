---
id: 0066
date: 2026-10-08
type: refactor
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Remove duplicated constants from the simulation modules
---
PERCENT and signed_unit live in mathx; CENTRE and REGULATION_PERIOD_S are reused instead of redefined; two different frame-x caps are renamed; Any is gone from config.py.
