---
id: 0055
date: 2026-10-07
type: added
scope: [cli]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the sim command and the text renderer
---
uv run sim --demo --seed 7 [--format text|ndjson] [--verbosity key|full] plays factory teams and prints a deterministic play-by-play plus a statistics table; --home/--away/--world/--db explain that a world is needed. Logic stays in cli/render.py (pure formatting) and the library.
