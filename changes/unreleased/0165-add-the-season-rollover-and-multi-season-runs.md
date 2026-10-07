---
id: 0165
date: 2026-10-07
type: added
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add the season rollover and multi-season runs
---
RolloverStage runs the day after a season ends: awards, club year-end (reputation, support, sponsors, budgets), retirements, contract renewals scaled to the wage budget, season-end progression with real playing time, academy intake, free-agent pool top-up and trim, squad rebalancing with entries, and the next season. SeasonRunner.run_seasons plays several seasons back to back.
