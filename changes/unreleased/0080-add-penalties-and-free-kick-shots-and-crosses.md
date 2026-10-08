---
id: 0080
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add penalties and free-kick shots and crosses
---
A called foul inside the box becomes a penalty (taker by named list or best taker, conversion about 75% for average players, outcomes goal/saved/missed/woodwork, goal or save caused by the penalty). Direct free kicks within 32 m are shot with xG cut by a wall factor, longer ones in the attacking half are crossed into the corner's aerial duel. Both only when restarts.enabled.
