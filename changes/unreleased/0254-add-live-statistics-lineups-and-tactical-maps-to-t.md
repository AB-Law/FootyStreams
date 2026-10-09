---
id: 0254
date: 2026-10-09
type: added
scope: [tools]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add live statistics, lineups and tactical maps to the pixel viewer
---
The viewer page gains a live stats panel (possession, field tilt, momentum, xG, shots, passes, tackles, pressing metric, distance and more), lineups with cards, goals and a form figure, and an analysis drawer with pass network, pass lines, press map, heatmap, shot map and shape, filterable by team, player and time window. All of it is computed in the browser from the replay's events and frames. record_match.py now writes each side's formation, lineup and bench into the meta file.
