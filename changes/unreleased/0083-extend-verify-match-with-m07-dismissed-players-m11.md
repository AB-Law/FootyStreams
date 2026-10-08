---
id: 0083
date: 2026-10-07
type: added
scope: [verify, sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Extend verify_match with M07 (dismissed players), M11 (card logic, men counts) and M12 (sequencing)
---
Checks live in verify/discipline.py and verify/sequencing.py with a shared id index; each has a crafted-violation test against a real card-heavy log. The card event's context now counts the men after a dismissal (like the score after a goal).
