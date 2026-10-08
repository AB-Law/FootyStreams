---
id: 0062
date: 2026-10-08
type: refactor
scope: [domain, verify, sim]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Share the one-player-on-two-teams check between sim and verify
---
players_on_both_sheets in domain/match.py is the single definition of invariant M05; sim.validate_setup and verify.check_rosters both call it.
