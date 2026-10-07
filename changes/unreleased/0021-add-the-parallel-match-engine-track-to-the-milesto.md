---
id: 0021
date: 2026-10-07
type: docs
scope: [design]
milestone: M0
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the parallel match-engine track to the milestone plan
---
Describes how the match engine (M4-M7) can be built by a second agent in parallel with the world track (M2, M3, M9-M11) after M1 is merged: track ownership, join points (M8, M12), plan changes that decouple the tracks (build_match_setup and lineup AI move to M9, a MatchSimulator Protocol with a ResultOnlySimulator, a factory-based sim --demo CLI, M1 provides MatchResult and the factories) and rules for worktrees, frozen contracts, shared files and fragment-id collisions. Follow-up before starting parallel work: make 'changelog check' detect duplicate fragment ids.
