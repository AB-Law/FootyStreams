---
id: 0074
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add the daily tick, matchday play and the season runner
---
DailyTick runs the ordered stages (recovery, life events, club admin, season end), each in its own transaction with a world_log row so a re-run skips what is done, then plays the day's fixtures (one transaction per match) and closes the matchday with a standings snapshot. SeasonRunner schedules a season and drives the tick to its last day. LeagueTables bundles the static tables; persistence errors and record types are re-exported through ports.
