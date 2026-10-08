---
id: 0243
date: 2026-10-09
type: fixed
scope: [sim]
milestone: M8
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Move the frame ball at ball speed through long dead moments
---
A moment can last 15 s (a throw-in delay), and frames interpolated the ball and the player who gets it over all of it, so the ball crawled. In moments longer than 5 s they now cover their distance at 25 m/s and then hold; team-mates still walk over the whole moment. Frames only; no change to the other events.
