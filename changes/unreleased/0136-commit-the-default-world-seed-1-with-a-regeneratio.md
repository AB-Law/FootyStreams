---
id: 0136
date: 2026-10-07
type: added
scope: [seed]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Commit the default world (seed 1) with a regeneration test
---
data/worlds/default is what 'uv run seed --seed 1 --name default' writes (294 players, 8 clubs, content_sha256 a373949b...). Tests regenerate seed 1 and compare every file byte for byte and the manifest, and run verify_world on the loaded files. Regenerate it with the same command whenever generation changes, as a separate data commit.
