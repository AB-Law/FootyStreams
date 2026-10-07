---
id: 0076
date: 2026-10-07
type: refactor
scope: [sim]
milestone: M6
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Build the state from a BuildContext and add the bench, injury stream and ManagerConfig
---
Preparation for substitutions and injuries: BuildContext (dayform stream, conditions, crowd, config) is shared by build_state and later by substitute building; Play carries the injury stream and the context; TeamState tracks bench, substituted-off players and substitution windows; ManagerConfig holds the substitution rules (disabled until M6 is enabled). Tests build states through make_state. No behaviour change.
