---
id: 0057
date: 2026-10-07
type: changed
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Damp skill effects and add the totality, strength and performance tests
---
A 5-point attribute gap gave an 88% win rate; damping pass/dribble/tackle skill swings (0.5/0.45/0.4 -> 0.12/0.12/0.10) and re-tuning progress_scale to 12 gives about 60% at gap 10 and 75% at gap 15 with ~3.0 goals a match (loose, M8 fits properly). Adds sim fuzz (8 setups in T0, 200 slow), statistical strength tests and the M4-match-budget tripwire.
