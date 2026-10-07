---
id: 0047
date: 2026-10-07
type: added
scope: [data]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: 'Add the player generator: archetypes, spiky attributes, positions, personality and contracts'
---
Attributes are level + shape offsets (position and archetype bias, correlated athleticism/technique/football-IQ factors, noise); the level is solved against domain ability_from_attributes so generated ability matches the target within 1. Also adds geography (Valmere with six regions, eight foreign nations), deterministic base-36 ids and the shared person identity builder.
