---
id: 0257
date: 2026-10-09
type: added
scope: [events, sim]
milestone: M8
breaking: false
schema_version_impact: minor
sim_version_impact: patch
config_impact: false
migration: false
summary: 'Record how a take-on is done: a skill move chosen from the dribbler''s ability and the situation'
---
Dribble events carry skill_move (knock past, step-over, drag-back, cut inside, nutmeg, roulette, rainbow flick, or None for a plain run). The choice depends on dribbling, flair, agility, balance and pace, the nearest defender's distance, the pressure and how wide the carrier is. It is a look for the renderer: the outcome is rolled first and unchanged, no random stream is drawn from, so goals and shots are the same.
