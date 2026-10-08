---
id: 0160
date: 2026-10-07
type: added
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add retirement
---
Retirement chance comes from an age table scaled by how far the player is below the league's mean ability; each player rolls on his own stream. Retired players lose contract and club but stay on record, and the feed gets a retirement event.
