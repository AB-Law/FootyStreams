---
id: 0054
date: 2026-10-07
type: added
scope: [sim, events]
milestone: M4
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add simulate_match, run_match, the match loop and an event-derived summary
---
MatchEngine sequences moments (positions, press tackle, decision, resolver) over two 45-minute periods with kickoff/halftime/fulltime; run_match returns the MatchResult. The summary (team and player stats, possession by event gaps) is a pure fold over the events; log_digest is a sha256 over the NDJSON of model_dump_json() lines (events/digest.py, shared with verify). Demo teams from tests/factories/sim_teams.py (fragment folded here).
