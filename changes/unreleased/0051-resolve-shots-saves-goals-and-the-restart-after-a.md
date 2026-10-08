---
id: 0051
date: 2026-10-07
type: added
scope: [sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Resolve shots, saves, goals and the restart after a goal
---
Outcome shares are built so the goal chance averages the shot's xG (on-target share = remainder after block, miss and woodwork; keeper rating bends the chance). Goals update the score before the goal event, then the conceding side kicks off after a celebration delay. Corners and goal kicks follow in M5.
