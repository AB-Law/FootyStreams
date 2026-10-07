---
id: 0148
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add weather generation and attendance
---
generate_weather draws match-day weather from the climate bands in climate.yaml by month, with rain, snow, fog, wind and daylight at kick-off; attendance fills the ground from reputation, form, derby status and weather within the configured floor.
