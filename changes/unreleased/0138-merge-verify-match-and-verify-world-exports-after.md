---
id: 0138
date: 2026-10-08
type: fixed
scope: [verify, schemas, sim]
milestone: M2
breaking: false
schema_version_impact: patch
sim_version_impact: patch
config_impact: false
migration: false
summary: Merge verify exports, renumber M2 fragments, and retie goldens after Track A rebase
---
After rebasing Track B onto main (M4-M7), keep both `verify_match` and `verify_world` in `verify/__init__.py`, renumber M2 fragments 0042-0058 to 0121-0137, bump SCHEMA_VERSION 0.3.0 -> 0.3.1 and SIM_VERSION 0.4.0 -> 0.4.1 so event stamps and goldens match, and refresh the default-world manifest.
