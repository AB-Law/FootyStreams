---
id: 0216
date: 2026-10-08
type: changed
scope: [sim, data, design]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: patch
config_impact: true
migration: false
summary: Allow five substitution windows and move the five-plus goals bands
---
The AI makes one change per stoppage, so three windows capped a side at 3.0 changes against 4.2 in a league; manager.max_windows is now 5 (4.18 measured). The balance targets for matches with five or more goals move from 4% (0-7) to 14% (10-18) and for one team from 1% to 2.5%: a Poisson fit at 2.7 goals gives 13.7%, and a published Premier League analysis puts six or more at 8.5%.
