---
id: 0152
date: 2026-10-07
type: changed
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Derive fixture ids and flag derbies when scheduling
---
Fixture ids are derived from the season, matchday and pairing instead of counted, so scheduling the same season always gives the same ids; fixtures between derby rivals carry is_derby.
