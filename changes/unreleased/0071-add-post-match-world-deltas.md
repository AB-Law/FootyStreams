---
id: 0071
date: 2026-10-07
type: added
scope: [league]
milestone: M9
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add post-match world deltas
---
derive_world_delta turns a finished match into one delta: the match row with both frozen sheets, fixture status, summary, event log, tired and sharper players with new form and morale, cards and bans, injuries with return dates from the injury catalog, career apps and goals, match bonuses, home takings, rule-based mood and news. Recovery config gains red-card ban length and injury severity weights.
