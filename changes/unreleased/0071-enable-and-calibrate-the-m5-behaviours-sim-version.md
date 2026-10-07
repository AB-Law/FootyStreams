---
id: 0071
date: 2026-10-07
type: changed
scope: [sim, schemas]
milestone: M5
breaking: false
schema_version_impact: patch
sim_version_impact: minor
config_impact: true
migration: false
summary: Enable and calibrate the M5 behaviours; SIM_VERSION 0.2.0
---
Switches on fouls, cards, restarts, penalties, free-kick shots, offside and added time with calibrated defaults (about 3.0 goals, 15 shots a side, 25 fouls, 3.6 cards, 3.4 offsides, 10 corners, 0.3 penalties a match). SIM_VERSION 0.1.0 -> 0.2.0, SCHEMA_VERSION 0.1.3 -> 0.1.4 (only the regenerated version defaults), goldens re-pinned with golden update. Done in one commit because the gate requires digests, version and defaults to move together.
