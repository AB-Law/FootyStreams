---
id: 0052
date: 2026-10-07
type: perf
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Speed up option generation and refresh positions every 4 seconds
---
Profile of 5 matches showed openness at ~30% of match time (call overhead): inlined in metres with squared distances (Perf: M4-match-budget). Options share one Situation computed per decision; positions refresh once 4 s of match time have passed (design 02 section 4); 4 candidate receivers plus the safe outlet.
