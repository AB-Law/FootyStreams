---
id: 0046
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add pressure model and pass, shot and dribble probability models
---
Pressure from the three nearest opponents, openness (own space + clear lane), pass classification and success, xG geometry anchored at 0.6/0.3/0.1/0.02 from 6/11/18/30 m, dribble success. Adds SimConfig groups pressure, passing, shot, dribble.
