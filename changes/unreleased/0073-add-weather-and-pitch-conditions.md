---
id: 0073
date: 2026-10-07
type: added
scope: [sim]
milestone: M6
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add weather and pitch conditions
---
WeatherConfig.enabled (off until M6 is enabled). conditions_for folds temperature, rain-soaked pitch (reduced by drainage), wind and pitch quality into bounded effects: long/through/cross pass penalty, first-touch and dribbling multipliers, an injury hazard multiplier and heat/cold for fatigue. build_state takes the config.
