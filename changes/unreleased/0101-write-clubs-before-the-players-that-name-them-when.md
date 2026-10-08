---
id: 0101
date: 2026-10-08
type: fixed
scope: [league]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Write clubs before the players that name them when applying a delta
---
On SQLite the foreign key from a contract to its club failed when one delta created the outside-world club and a player signed with it; memory has no foreign keys so only the slow resume test noticed.
