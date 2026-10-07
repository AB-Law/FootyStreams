---
id: 0045
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add mutable match state and the positioning model
---
state.py (slots dataclasses, the only mutable sim state), formation-slot targets shifted by line height, width, possession and ball side, speed-limited movement, kick-off placement. Adds SimConfig.positioning.
