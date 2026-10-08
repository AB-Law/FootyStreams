---
id: 0153
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the world clock and daily recovery
---
WorldClock keeps the in-world date in world_meta. recover and decay_sharpness settle fatigue, fitness and morale, heal injuries into the history, and decay sharpness weekly; life events are now rolled weekly with the chance of at least one event in the window (roll_interval_days).
