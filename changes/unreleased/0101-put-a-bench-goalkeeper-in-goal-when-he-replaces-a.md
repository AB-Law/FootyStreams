---
id: 0101
date: 2026-10-08
type: fixed
scope: [sim]
milestone: M6
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Put a bench goalkeeper in goal when he replaces a stand-in keeper
---
A substitute now takes the departing player's pitch spot (position and base spot) instead of the formation slot's, so a bench goalkeeper replacing an injured stand-in keeper goes in goal rather than into an outfield slot with no goalkeeper on the pitch. build_player takes the FormationSlot it fills.
