---
id: 0072
date: 2026-10-08
type: changed
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: patch
config_impact: true
migration: false
summary: Bound the SimConfig knobs and move the remaining magic numbers into it
---
Every numeric SimConfig knob is bounded; shot.off_target_min/max and decision.min_utility_weight replace magic numbers; cross-field validators keep blocked + off-target below 1. The new fields change config_hash, hence the sim version bump.
