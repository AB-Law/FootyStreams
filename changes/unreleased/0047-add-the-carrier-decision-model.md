---
id: 0047
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the carrier decision model
---
Threat surface, pass/dribble/shot/clear options with utilities (progression, keeping, risk, tactics and game-state biases) and a rational-weight softmax that consumes one draw. Adds SimConfig.decision.
