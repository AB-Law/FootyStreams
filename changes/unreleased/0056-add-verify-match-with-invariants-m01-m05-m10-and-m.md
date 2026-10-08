---
id: 0056
date: 2026-10-07
type: added
scope: [verify]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add verify_match with invariants M01-M05, M10 and M17
---
Single implementation of the first match invariants: seq contiguity, ids, non-decreasing clock/tick, running score vs goals (incl. fulltime and summary), no player on both sheets, positions in the pitch, log ends fulltime then summary. Later milestones extend the catalogue.
