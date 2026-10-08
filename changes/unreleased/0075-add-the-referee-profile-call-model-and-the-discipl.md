---
id: 0075
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the referee profile, call model and the discipline and setpiece streams
---
simulate_match/run_match take an optional Referee (MatchSetup carries only referee_id); without one a neutral referee officiates. Call probability squash((severity - threshold)/scale) with strictness, consistency noise and a crowd-scaled home tilt. Play now carries the discipline and setpiece streams. No change to M4 output yet.
