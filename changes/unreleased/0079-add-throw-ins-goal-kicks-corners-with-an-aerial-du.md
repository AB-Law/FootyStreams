---
id: 0079
date: 2026-10-07
type: added
scope: [sim]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add throw-ins, goal kicks, corners with an aerial duel and out-of-play detection
---
RestartConfig.enabled (off until M5 is enabled): overhit passes that leave the pitch, shots off target (goal kick), blocked/parried shots and blocked crosses behind (corner), clearances and heavy touches into touch (throw-in). Corner: taker by flag side, attackers sent into the box vs the best five defenders, delivery lifts the attackers' share; outcomes keeper claim, header shot through the normal shot model, or clearance with a second-ball contest. Draws from the setpiece stream.
