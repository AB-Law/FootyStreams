---
id: 0147
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add rule-based modifiers and the world-event generator
---
Modifiers are created from match facts (derby hero, confidence surge, blamed for defeat), from long-injury returns, and by a seeded per-player life-event generator that also writes the public WorldEvent feed. Rule thresholds live in mood.yaml (config impact).
