---
id: 0185
date: 2026-10-08
type: fixed
scope: [verify]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Export check_transfers from the verify package
---
check_transfers was listed in __all__ and used by the L06 canary tests, but never imported from verify.league, so mypy and pytest both failed on the package export.
