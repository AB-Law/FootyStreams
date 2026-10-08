---
id: 0184
date: 2026-10-08
type: build
scope: [tools]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Cap coverage pytest-xdist workers to avoid CI OOM crashes
---
The PR-tier coverage run kept `-n auto`, which spawned enough traced workers to crash
Windows CI processes. Coverage now uses two workers; the fast tier still uses `-n auto`.
