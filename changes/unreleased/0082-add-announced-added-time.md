---
id: 0082
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add announced added time
---
StoppageConfig.enabled (off until M5 is enabled): goals' celebrations and card delays accumulate as stoppage; at the end of each period an added_time event announces ceil(generosity x stoppage minutes x 0.65) clamped [1,8] / [2,10] and play continues that long. The summary's duration and possession fold now work per period.
