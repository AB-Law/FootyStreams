---
id: 0225
date: 2026-10-08
type: fixed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: patch
config_impact: true
migration: false
summary: Count a denied goal-scoring chance only when it was a clear chance
---
Almost every red card (1.4 of 1.6 a match) was 'denying an opportunity': any foul on a man past x 0.78 with only the keeper ahead. A new discipline.dogso_min_xg (0.15) also asks for an unpressured xG at that spot, so a wide or 16 m run past the last defender is not a denied goal. Reds fall from 1.45 to 0.31 a match.
