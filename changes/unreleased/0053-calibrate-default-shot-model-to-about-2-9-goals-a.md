---
id: 0053
date: 2026-10-07
type: changed
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Calibrate default shot model to about 2.9 goals a match
---
With position-aware teams, 12-14 shots a side at 10% conversion and 40% on target: xg_cap 0.75 -> 0.40, pressure_penalty 0.5 -> 0.7, block 0.12, off target 0.43, shot_scale 7 -> 16. Rough calibration only; the balance harness (M8) fits the knobs properly.
