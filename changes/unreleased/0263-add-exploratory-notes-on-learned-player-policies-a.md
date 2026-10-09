---
id: 0263
date: 2026-10-09
type: docs
scope: [design]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add exploratory notes on learned player policies and engine compute
---
Notes from a design discussion, not a decision: a per-player decision seam with reason codes and intent events, player quality as rating-driven dials rather than per-tier models, learning policies from scratch or by self-play, and measured and estimated costs of staying in Python, moving the hot loop to Rust, or building a GPU environment.
