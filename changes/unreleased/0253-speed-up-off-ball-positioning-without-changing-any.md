---
id: 0253
date: 2026-10-09
type: perf
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Speed up off-ball positioning without changing any match
---
Marking shares one list of opponents in the team's frame between the two passes, support angles ignore rivals too far to matter and frame conversion is inlined. Output is byte-identical (goldens unchanged); a match is about 10% cheaper, which keeps the performance tripwire from flaking under the gate's parallel load.
