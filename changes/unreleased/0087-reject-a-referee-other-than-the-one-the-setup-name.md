---
id: 0087
date: 2026-10-08
type: fixed
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Reject a referee other than the one the setup names
---
`simulate_match` / `run_match` take the `Referee` as an optional argument because `MatchSetup` carries only `referee_id`. Passing a referee with a different id silently simulated the match with the wrong official; it now raises `InvalidSetupError`. Omitting the referee still means the neutral one. No change to match output.
