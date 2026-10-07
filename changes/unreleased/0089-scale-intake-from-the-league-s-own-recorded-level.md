---
id: 0089
date: 2026-10-07
type: changed
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Scale intake from the league's own recorded level; split the rollover modules
---
Intake and journeymen are scaled from the level the league had at its first rollover (stored in world_meta), which removes the feedback loop that made ability drift upward; the rollover is split into state, squads and orchestration modules to respect the module size limit.
