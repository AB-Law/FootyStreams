---
id: 0064
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the MatchSimulator seam and the result-only simulator
---
ResultOnlySimulator plays a deterministic score from team strength, mood, form and fatigue and emits typed goal, card and injury events plus a summary; EventSimulator is a thin adapter around an injected run_match. Tunables live in the result_only block of league.yaml.
