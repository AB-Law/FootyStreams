---
id: 0063
date: 2026-10-07
type: fixed
scope: [cli]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Ignore the config hash when comparing golden digests
---
Adding a config knob changes config_hash but no match; only digests are the golden contract.
