---
id: 0149
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add match setup building and the lineup AI
---
build_match_setup freezes both sides for a fixture: availability (injuries, suspensions), globally best slot assignment with fatigue rotation, bench with a keeper, set-piece takers, and player snapshots carrying the resolved mood.
