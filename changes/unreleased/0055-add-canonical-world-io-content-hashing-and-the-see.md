---
id: 0055
date: 2026-10-07
type: added
scope: [cli]
milestone: M2
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add canonical world IO, content hashing and the seed CLI
---
seed/world_io.py writes a World as canonical JSON (sorted keys, 2-space indent, LF, trailing newline) with a manifest carrying the content_sha256, and reads it back validating every row and the hash. 'uv run seed --seed N [--out DIR] [--name NAME] [--clubs K] [--validate] [--world DIR]' generates, runs the coherence checks and writes; exit codes 0/1/2. A cross-process test with a random PYTHONHASHSEED proves the same hash. Contracts are embedded in player, manager and staff rows (as in the M1 models) so there is no separate contracts.json. Fixes unrounded Unit values written by model_copy in the default-tactics blend (caught by the round-trip test).
