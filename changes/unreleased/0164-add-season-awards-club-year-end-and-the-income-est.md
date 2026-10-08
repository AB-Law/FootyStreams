---
id: 0164
date: 2026-10-07
type: added
scope: [league]
milestone: M10
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add season awards, club year-end and the income estimate
---
season_totals fold match summaries into per-player totals; season_awards produce the champion, top scorer and player-of-the-season events and award_modifiers the trophy and award glow. Clubs' reputation, fan base and board confidence follow the finish against expectation, sponsors renew, and the wage budget is reset from an income estimate built from the club's state. Rollover parameters live in development.yaml.
