---
id: 0090
date: 2026-10-07
type: added
scope: [sim]
milestone: M6
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add home advantage through the crowd
---
HomeAdvantageConfig.enabled (off until M6 is enabled). crowd = fill x mean(atmosphere, proximity, passion) x 2 x crowd weight (a deviation from the product in 02 section 8, which would be tiny with defaults). Home mental attributes up to +2.5% x crowd x big_match; away composure down to -2% x crowd x toxicity; all scaled by SimConfig.home_advantage_scale. Away travel/altitude drain is in fatigue.
