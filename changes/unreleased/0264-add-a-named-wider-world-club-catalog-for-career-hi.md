---
id: 0264
date: 2026-10-09
type: added
scope: [seed, domain, persistence, schemas, data]
milestone: design
breaking: false
schema_version_impact: minor
sim_version_impact: patch
config_impact: false
migration: true
summary: Add a named wider-world club catalog for career history
---
Adds `WiderClub` and `wider_clubs.json` (40 stubs, ids `clb_wd001`…`clb_wd040`) so player and
manager prior stints are speakable in commentary. Regenerates `data/worlds/default`
(`GENERATOR_VERSION` 1.1.0, `SCHEMA_VERSION` 0.8.0). Alembic revision `0002` creates the
`wider_clubs` table. `SIM_VERSION` 0.7.6 re-pins goldens for the new `schema_version` string
in events (match play unchanged).
