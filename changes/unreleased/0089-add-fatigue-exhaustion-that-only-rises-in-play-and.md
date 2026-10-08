---
id: 0089
date: 2026-10-07
type: added
scope: [sim]
milestone: M6
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Add fatigue: exhaustion that only rises in play and weakens skills'
---
FatigueConfig.enabled (off until M6 is enabled). Starting exhaustion from carried fatigue and fitness; drain from stamina, fitness, work rate, role, pressing, tempo, heat, wet pitch, travel and playing a man down; skills rebuilt from base_skills when exhaustion crosses a 0.05 step (physical first, then technical, then mental); half-time recovery is the only decrease. build.py now builds the state (moved out of state.py); MatchEngine.state exposes the live state for tests.
