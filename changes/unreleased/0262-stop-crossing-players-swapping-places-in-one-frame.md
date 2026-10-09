---
id: 0262
date: 2026-10-09
type: fixed
scope: [tools]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Stop crossing players swapping places in one frame in the pixel viewer
---
Two players whose paths cross used to swap places in a single frame (the push that keeps them a body's width apart flipped sides). The push is now averaged over the moments around the time shown, so they slide past each other.
