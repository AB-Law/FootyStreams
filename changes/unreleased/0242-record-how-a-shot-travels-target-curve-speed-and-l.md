---
id: 0242
date: 2026-10-09
type: added
scope: [events]
milestone: M8
breaking: false
schema_version_impact: minor
sim_version_impact: minor
config_impact: false
migration: false
summary: 'Record how a shot travels: target, curve, speed and loft'
---
ShotEvent gains target, curve, speed_mps and loft (SCHEMA_VERSION 0.4.0), drawn from a separate flight stream (sim/flight.py) so no other draw moves. Presentation data for the broadcast; the outcome is decided first. Absent with the context off.
