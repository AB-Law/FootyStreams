---
id: 0094
date: 2026-10-07
type: added
scope: [league]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add transfer windows and needs analysis
---
windows_for derives the summer and mid-season windows of a season from the calendar (ids from season and kind); analyse() lists a club's needs by position group: groups below their minimum are urgent, weak starters ask for a better player.
