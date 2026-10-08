---
id: 0220
date: 2026-10-08
type: changed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: patch
sim_version_impact: minor
config_impact: true
migration: false
summary: Move the yellow-card substitution window to minutes 60-85
---
A manager pulled a booked, aggressive player from minute 25, so about 0.8 matches in 1 had a tactical change before half-time. Real managers do it late. The window is now minutes 60 to 85 (manager.yellow_from_min, yellow_until_min); SIM_VERSION 0.5.0 and the goldens are re-pinned.
