---
id: 0049
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Resolve passes: completion, interception, loose ball and out of play'
---
Play bundle, possession hand-over (new chain on side change), tackle attempts under pressure, interceptor choice weighted by lane distance and reading, tempo-scaled durations. Adds SimConfig.tempo and SimConfig.challenge. Out-of-play restarts arrive in M5; until then possession goes to the nearest opponent.
